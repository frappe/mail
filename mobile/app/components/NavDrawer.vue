<template>
	<!-- Full-screen overlay. Single-cell GridLayout: backdrop fills it, panel sits
	     on the left on top. Android collapses it when closed (removed from layout and
	     hit-testing). iOS instead keeps it laid out but non-interactive, because iOS
	     drops the panel's child margins if its first layout runs off-screen/collapsed;
	     see onPanelLoaded. -->
	<GridLayout :visibility="overlayVisibility" :isUserInteractionEnabled="visible">
		<StackLayout class="bg-surface-gray-7" @loaded="onBackdropLoaded" @tap="$emit('close')" />

		<!-- Styling lives in Tailwind classes rather than inline attributes:
		     iOS does not reliably honour inline padding / GridLayout sizing here.
		     Horizontal insets are expressed as margins on child views rather than
		     padding on the container, because iOS ignores horizontal padding on
		     layout containers (GridLayout/StackLayout) while honouring margins. -->
		<GridLayout
			width="300"
			horizontalAlignment="left"
			rows="auto, *, auto"
			class="bg-surface-white"
			@loaded="onPanelLoaded"
			@tap="() => {}"
		>
			<!-- Account header — tap opens the account sheet (switch account/site,
			     settings, sign out). Direct grid child so columns lay out on iOS. -->
			<GridLayout
				row="0"
				columns="42, *, 42"
				class="py-3.5"
				:marginTop="safeTop"
				@tap="$emit('open-account')"
			>
				<GridLayout col="0" class="ml-10 h-11 w-11" verticalAlignment="center">
					<Image :src="logoSrc" stretch="aspectFit" class="h-11 w-11 rounded-xl" />
				</GridLayout>
				<StackLayout col="1" class="ml-7" verticalAlignment="center">
					<Label :text="title" class="mb-0.5 text-base font-bold" />
					<Label
						v-if="subtitle"
						:text="subtitle"
						class="text-ink-gray-5 text-sm"
						textWrap="false"
					/>
				</StackLayout>
				<GridLayout col="2" class="mr-8 h-9 w-9 rounded-full" verticalAlignment="center">
					<Label
						:text="lucide('chevron-down')"
						class="font-lucide text-ink-gray-6 text-lg"
						horizontalAlignment="right"
						verticalAlignment="center"
					/>
				</GridLayout>
			</GridLayout>

			<!-- Folder sections -->
			<ScrollView row="1">
				<StackLayout>
					<template v-for="section in sections" :key="section.label">
						<Label
							:text="section.label"
							class="text-ink-gray-4 ml-6 mr-4 pb-2 pt-4 text-xs font-semibold uppercase"
							textWrap="false"
						/>
						<GridLayout
							v-for="item in section.items"
							:key="item.label"
							columns="auto, *, auto"
							class="mx-2 rounded-xl py-3"
							:class="{ 'bg-surface-gray-2': item.label === activeLabel }"
							@tap="item.onTap"
						>
							<Label
								col="0"
								:text="lucide(item.icon)"
								class="font-lucide ml-3.5 text-xl"
								:class="item.colorClass ? item.colorClass : 'text-ink-gray-6'"
								verticalAlignment="center"
							/>
							<Label
								col="1"
								:text="item.label"
								:class="
									item.label === activeLabel
										? 'ml-3.5 font-bold'
										: 'ml-3.5 font-medium'
								"
								verticalAlignment="center"
							/>
							<Label
								v-if="item.suffix"
								col="2"
								:text="item.suffix"
								class="text-ink-gray-5 mr-3.5 text-sm font-medium"
								verticalAlignment="center"
							/>
						</GridLayout>
					</template>
					<StackLayout height="12" />
				</StackLayout>
			</ScrollView>

			<!-- Storage meter -->
			<StackLayout
				v-if="showStorage"
				row="2"
				class="border-outline-gray-1 border-t pb-5 pt-3.5"
				:marginBottom="safeBottom"
			>
				<!-- Inner wrapper carries the horizontal inset as a margin. It must be a
				     GridLayout, not a StackLayout: on iOS, horizontal margins are honoured
				     on GridLayout but ignored on StackLayout (and padding is ignored on
				     both). -->
				<GridLayout rows="auto, auto, auto" class="mx-5">
					<StackLayout row="0" orientation="horizontal" class="mb-2.5">
						<Label
							:text="lucide('cloud')"
							class="font-lucide text-xl"
							verticalAlignment="center"
						/>
						<Label
							:text="__('Storage')"
							class="ml-2.5 font-semibold"
							verticalAlignment="center"
						/>
					</StackLayout>
					<GridLayout row="1" class="bg-surface-gray-2 h-1.5 rounded-full">
						<StackLayout
							class="h-1.5 rounded-full"
							:class="storageOverLimit ? 'bg-surface-red-6' : 'bg-surface-gray-7'"
							:width="storagePercent + '%'"
							horizontalAlignment="left"
						/>
					</GridLayout>
					<Label row="2" :text="storageLabel" class="text-ink-gray-5 mt-2 text-xs" />
				</GridLayout>
			</StackLayout>
		</GridLayout>
	</GridLayout>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { CoreTypes, isIOS } from '@nativescript/core'

import { formatBytes } from '@/utils/format'
import { folderColorClass, lucide, mailboxIcon } from '@/utils/lucide'
import { safeAreaBottom, safeAreaTop } from '@/utils/safeArea'
import { siteStore } from '@/stores/site'
import { userStore } from '@/stores/user'

import type { MailboxData, UserAccount } from '@mail/types'
import type { EventData, View } from '@nativescript/core'

const props = defineProps<{ open: boolean; activeLabel: string }>()
const emit = defineEmits<{ close: []; select: [label: string]; 'open-account': [] }>()

const site = siteStore()
const store = userStore()

const PANEL_WIDTH = 300
const customLabel = __('Custom')

const visible = ref(false)
const safeTop = safeAreaTop()
const safeBottom = safeAreaBottom()

// Android removes the overlay from layout + hit-testing when closed; iOS keeps it
// laid out (hidden via opacity, non-interactive) so the panel's margins survive.
const overlayVisibility = computed(() => (isIOS || visible.value ? 'visible' : 'collapse'))

// Native views captured on @loaded so we can animate the slide/fade directly.
let panelView: View | null = null
let backdropView: View | null = null

// Mirrors AppSidebar: the brand name, or 'Mail' for the default Frappe branding.
const title = computed(() => {
	const name = site.activeSite?.app_name
	return name && name !== 'Frappe' && name !== 'Frappe Mail' ? name : 'Mail'
})

// The site logo when it's a raster the native Image can render (NativeScript can't
// render SVG/ICO without a plugin); otherwise the bundled Frappe Mail logo.
const logoSrc = computed(() => {
	const logo = site.activeSite?.logo
	if (logo && /\.(png|jpe?g|gif|webp)$/i.test(logo)) {
		return logo.startsWith('http') ? logo : `${site.activeSite?.url ?? ''}${logo}`
	}
	return '~/images/mail-logo.png'
})

const accounts = computed<UserAccount[]>(() => store.user?.accounts ?? [])

// Mirrors AppSidebar: the active account's name, or the user's full name for a
// personal account / when no account is resolved.
const subtitle = computed(() => {
	const current = accounts.value.find((a) => a.id === store.accountId)
	if (!current || current.is_personal) return store.user?.full_name || ''
	return current._name
})

// Storage meter — mirrors the web QuotaBar. The bar fill is capped at 100% and
// turns red past 80% usage; the label shows usage out of the disk quota, or the
// raw amount used when the quota is unlimited (disk_quota <= 0).
const showStorage = computed(() => store.user?.is_jmap_configured && store.quota)
const storagePercent = computed(() => Math.min(store.quota?.used_percentage ?? 0, 100))
const storageOverLimit = computed(() => (store.quota?.used_percentage ?? 0) > 80)
const storageLabel = computed(() => {
	const q = store.quota
	if (!q) return ''
	if (q.disk_quota <= 0) return __('Unlimited ({0} used)', [formatBytes(q.used_quota)])
	return __('{0}% of {1} used', [q.used_percentage.toFixed(2), formatBytes(q.disk_quota)])
})

const subscribed = computed(() => store.mailboxes.filter((m) => m.subscribed))
const mailboxSuffix = (m: MailboxData) =>
	m.unread_threads ? m.unread_threads.toLocaleString() : ''

// Default (role mailboxes + Starred), Custom (user folders), People.
const sections = computed(() => {
	const toItem = (m: MailboxData) => ({
		label: m._name,
		suffix: mailboxSuffix(m),
		icon: mailboxIcon(m),
		colorClass: folderColorClass(m.color),
		onTap: () => select(m._name),
	})
	const defaultItems = [
		...subscribed.value.filter((m) => m.role).map(toItem),
		{
			label: __('Starred'),
			suffix: '',
			icon: 'star',
			colorClass: '',
			onTap: () => select(__('Starred')),
		},
	]
	const customItems = subscribed.value.filter((m) => !m.role).map(toItem)
	const peopleItems = [
		{
			label: __('Address Books'),
			suffix: '',
			icon: 'book-user',
			colorClass: '',
			onTap: () => select(__('Address Books')),
		},
		{
			label: __('Contacts'),
			suffix: '',
			icon: 'contact-round',
			colorClass: '',
			onTap: () => select(__('Contacts')),
		},
	]

	return [
		{ label: __('Default'), items: defaultItems },
		{ label: customLabel, items: customItems },
		{ label: __('People'), items: peopleItems },
	]
})

function select(label: string) {
	emit('select', label)
	emit('close')
}

// iOS only: the panel's *resting* (closed) position must be translateX:0 — on-screen
// — hidden with opacity rather than a transform. On iOS the panel's child margins are
// dropped if its decisive layout pass runs while it is shifted off the left edge (the
// GridLayout safe-area inset math keys off the window position), and translateX does
// not trigger a re-layout, so it can never recover. Keeping it laid out at x:0 means
// margins are always computed correctly; the slide is a transient transform only.
// Android has no such bug and is collapsed when closed, so it rests off-screen.
function onPanelLoaded(args: EventData) {
	panelView = args.object as View
	if (isIOS) {
		panelView.translateX = 0
		panelView.opacity = 0
	} else {
		panelView.translateX = -PANEL_WIDTH
	}
}

function onBackdropLoaded(args: EventData) {
	backdropView = args.object as View
	backdropView.opacity = 0
}

watch(
	() => props.open,
	(open) => (open ? openDrawer() : closeDrawer()),
)

function openDrawer() {
	visible.value = true
	nextTick(() => {
		if (!panelView || !backdropView) return
		panelView.opacity = 1
		panelView.translateX = -PANEL_WIDTH
		panelView.animate({
			translate: { x: 0, y: 0 },
			duration: 220,
			curve: CoreTypes.AnimationCurve.easeOut,
		})
		backdropView.animate({ opacity: 0.5, duration: 220 })
	})
}

function closeDrawer() {
	if (!panelView || !backdropView) {
		visible.value = false
		return
	}
	Promise.all([
		panelView.animate({
			translate: { x: -PANEL_WIDTH, y: 0 },
			duration: 200,
			curve: CoreTypes.AnimationCurve.easeIn,
		}),
		backdropView.animate({ opacity: 0, duration: 200 }),
	])
		.catch(() => {})
		.finally(() => {
			// iOS: return to the on-screen resting position (hidden via opacity) so a
			// future layout pass keeps the child margins. Android: leave it off-screen;
			// it gets collapsed out of layout below.
			if (panelView && isIOS) {
				panelView.translateX = 0
				panelView.opacity = 0
			}
			visible.value = false
		})
}
</script>
