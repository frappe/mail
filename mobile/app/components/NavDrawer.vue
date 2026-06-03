<template>
	<!-- Full-screen overlay. Single-cell GridLayout: backdrop fills it, panel sits
	     on the left on top. Collapsed entirely when closed so it intercepts no taps. -->
	<GridLayout :visibility="visible ? 'visible' : 'collapse'">
		<StackLayout
			class="nd-backdrop bg-surface-gray-7"
			@loaded="onBackdropLoaded"
			@tap="$emit('close')"
		/>

		<!-- Styling lives in <style> (CSS classes) rather than inline attributes:
		     iOS does not reliably honour inline padding / GridLayout sizing here,
		     whereas CSS is applied consistently on both platforms. -->
		<GridLayout
			width="300"
			horizontalAlignment="left"
			rows="auto, *, auto"
			class="nd-panel bg-surface-white"
			@loaded="onPanelLoaded"
		>
			<!-- Account header — tap opens the account sheet (switch account/site,
			     settings, sign out). Direct grid child so columns lay out on iOS. -->
			<GridLayout
				row="0"
				columns="42, *, 34"
				class="nd-header"
				:marginTop="safeTop"
				@tap="$emit('open-account')"
			>
				<GridLayout col="0" class="nd-logobox" verticalAlignment="center">
					<Image :src="logoSrc" stretch="aspectFit" class="nd-logo-img" />
				</GridLayout>
				<StackLayout col="1" class="nd-name" verticalAlignment="center">
					<Label :text="title" class="nd-title font-bold" />
					<Label
						v-if="subtitle"
						:text="subtitle"
						class="nd-sub text-ink-gray-5"
						textWrap="false"
					/>
				</StackLayout>
				<GridLayout col="2" class="nd-chevron" verticalAlignment="center">
					<Label
						:text="lucide('chevron-down')"
						class="nd-chevron-label text-ink-gray-6"
						horizontalAlignment="center"
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
							class="nd-section text-ink-gray-4 text-xs font-semibold uppercase"
							textWrap="false"
						/>
						<GridLayout
							v-for="item in section.items"
							:key="item.label"
							columns="auto, *, auto"
							:class="
								item.label === activeLabel ? 'nd-row bg-surface-gray-2' : 'nd-row'
							"
							@tap="item.onTap"
						>
							<Label
								col="0"
								:text="lucide(item.icon)"
								class="nd-row-icon text-[21px]"
								:class="item.colorClass ? item.colorClass : 'text-ink-gray-6'"
								verticalAlignment="center"
							/>
							<Label
								col="1"
								:text="item.label"
								:class="
									item.label === activeLabel
										? 'nd-label ml-3.5 font-bold'
										: 'nd-label ml-3.5 font-medium'
								"
								verticalAlignment="center"
							/>
							<Label
								v-if="item.suffix"
								col="2"
								:text="item.suffix"
								class="nd-count text-ink-gray-5 text-sm font-medium"
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
				class="nd-storage border-outline-gray-1 border-t"
				:marginBottom="safeBottom"
			>
				<StackLayout orientation="horizontal" class="nd-storage-head">
					<Label
						:text="lucide('cloud')"
						class="nd-storage-icon text-2xl"
						verticalAlignment="center"
					/>
					<Label
						:text="__('Storage')"
						class="nd-storage-title ml-2.5 font-semibold"
						verticalAlignment="center"
					/>
				</StackLayout>
				<GridLayout class="nd-track bg-surface-gray-2 h-1.5 rounded-full">
					<StackLayout
						class="nd-fill h-1.5 rounded-full"
						:class="storageOverLimit ? 'bg-surface-red-6' : 'bg-surface-gray-7'"
						:width="storagePercent + '%'"
						horizontalAlignment="left"
					/>
				</GridLayout>
				<Label :text="storageLabel" class="nd-storage-sub text-ink-gray-5 mt-2" />
			</StackLayout>
		</GridLayout>
	</GridLayout>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { CoreTypes } from '@nativescript/core'

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

function onPanelLoaded(args: EventData) {
	panelView = args.object as View
	panelView.translateX = -PANEL_WIDTH
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
		panelView.translateX = -PANEL_WIDTH
		backdropView.opacity = 0
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
		.finally(() => (visible.value = false))
}
</script>

<!-- Design tokens (espresso, light theme) from the Claude Design handoff. CSS is
     used instead of inline attributes because iOS applies it reliably. Icons use
     the bundled Lucide font (app/fonts/lucide.ttf, family "lucide"). -->
<style scoped>
.nd-header {
	padding: 14 16;
}
.nd-logobox {
	width: 42;
	height: 42;
}
.nd-logo-img {
	width: 42;
	height: 42;
	border-radius: 12;
}
.nd-name {
	margin-left: 12;
}
.nd-title {
	font-size: 16.5;
}
.nd-sub {
	font-size: 13.5;
}
.nd-chevron {
	width: 34;
	height: 34;
	border-radius: 34;
}
.nd-chevron-label {
	font-family: 'lucide';
	font-size: 18;
}

.nd-section {
	/* left padding aligns the label with the row icon column
	   (row margin-left 8 + row padding-left 14) */
	padding: 16 16 7 22;
}

.nd-row {
	padding: 11 14;
	margin-left: 8;
	margin-right: 8;
	border-radius: 13;
}
.nd-row-icon {
	font-family: 'lucide';
}

.nd-storage {
	padding: 14 18 18;
}
.nd-storage-head {
	margin-bottom: 10;
}
.nd-storage-icon {
	font-family: 'lucide';
}
.nd-storage-sub {
	font-size: 12.5;
}
</style>
