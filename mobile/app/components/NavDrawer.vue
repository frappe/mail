<template>
	<!-- Full-screen overlay. Single-cell GridLayout: backdrop fills it, panel sits
	     on the left on top. Collapsed entirely when closed so it intercepts no taps. -->
	<GridLayout :visibility="visible ? 'visible' : 'collapse'">
		<StackLayout
			@loaded="onBackdropLoaded"
			backgroundColor="rgba(0, 0, 0, 0.5)"
			@tap="$emit('close')"
		/>

		<GridLayout
			@loaded="onPanelLoaded"
			width="300"
			horizontalAlignment="left"
			rows="auto, *, auto"
			class="bg-surface-white"
		>
			<!-- Header: brand + current account -->
			<StackLayout row="0" class="border-b p-4">
				<Label :text="title" class="text-ink-gray-9 text-xl font-bold" textWrap="true" />
				<Label
					v-if="subtitle"
					:text="subtitle"
					class="text-ink-gray-5 mt-0.5 text-sm"
					textWrap="true"
				/>
			</StackLayout>

			<!-- Scrollable sections -->
			<ScrollView row="1">
				<StackLayout class="p-2">
					<template v-for="section in sections" :key="section.label">
						<Label
							:text="section.label"
							class="text-ink-gray-5 mb-1 mt-3 px-2 text-xs font-semibold uppercase"
						/>
						<GridLayout
							v-for="item in section.items"
							:key="item.label"
							columns="*, auto"
							class="rounded-lg px-2 py-3"
							:class="item.label === activeLabel ? 'bg-surface-gray-3' : ''"
							@tap="item.onTap"
						>
							<Label
								col="0"
								:text="item.label"
								class="text-ink-gray-8 text-base"
								textWrap="true"
							/>
							<Label
								v-if="item.suffix"
								col="1"
								:text="item.suffix"
								class="text-ink-gray-5 text-sm"
							/>
						</GridLayout>
					</template>
				</StackLayout>
			</ScrollView>

			<!-- Footer: account switcher (multi-account), settings, logout -->
			<StackLayout row="2" class="border-t p-2">
				<template v-if="accounts.length > 1">
					<StackLayout v-if="showAccounts">
						<GridLayout
							v-for="a in accounts"
							:key="a.id"
							columns="*, auto"
							class="rounded-lg px-2 py-3"
							@tap="switchAccount(a)"
						>
							<Label col="0" :text="a._name" class="text-ink-gray-8 text-base" />
							<Label
								v-if="a.id === store.accountId"
								col="1"
								text="✓"
								class="text-ink-blue-3 text-base"
							/>
						</GridLayout>
					</StackLayout>
					<GridLayout
						columns="*, auto"
						class="rounded-lg px-2 py-3"
						@tap="toggleAccounts"
					>
						<Label
							col="0"
							:text="__('Switch account')"
							class="text-ink-gray-8 text-base"
						/>
						<Label col="1" :text="showAccounts ? '▴' : '▾'" class="text-ink-gray-5" />
					</GridLayout>
				</template>

				<StackLayout class="rounded-lg px-2 py-3" @tap="openSettings">
					<Label :text="__('Settings')" class="text-ink-gray-8 text-base" />
				</StackLayout>
				<StackLayout class="rounded-lg px-2 py-3" @tap="$emit('logout')">
					<Label :text="__('Log out')" class="text-ink-red-3 text-base" />
				</StackLayout>
			</StackLayout>
		</GridLayout>
	</GridLayout>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { CoreTypes } from '@nativescript/core'

import { siteStore } from '@/stores/site'
import { userStore } from '@/stores/user'

import type { MailboxData, UserAccount } from '@mail/types'
import type { EventData, View } from '@nativescript/core'

const props = defineProps<{ open: boolean; activeLabel: string }>()
const emit = defineEmits<{ close: []; select: [label: string]; logout: [] }>()

const site = siteStore()
const store = userStore()

const PANEL_WIDTH = 300

const visible = ref(false)
const showAccounts = ref(false)

// Native views captured on @loaded so we can animate the slide/fade directly.
let panelView: View | null = null
let backdropView: View | null = null

const title = computed(() => site.activeSite?.app_name || 'Mail')
const subtitle = computed(() => {
	const current = accounts.value.find((a) => a.id === store.accountId)
	return current?._name || store.user?.full_name || ''
})
const accounts = computed<UserAccount[]>(() => store.user?.accounts ?? [])

const subscribed = computed(() => store.mailboxes.filter((m) => m.subscribed))
const mailboxLabel = (m: MailboxData) => m._name
const mailboxSuffix = (m: MailboxData) => (m.unread_threads ? String(m.unread_threads) : '')

// Section model mirrors the web AppSidebar: Default (role mailboxes + Starred),
// Custom (user folders), People (address books / contacts).
const sections = computed(() => {
	const toItem = (m: MailboxData) => ({
		label: mailboxLabel(m),
		suffix: mailboxSuffix(m),
		onTap: () => select(mailboxLabel(m)),
	})
	const defaultItems = [
		...subscribed.value.filter((m) => m.role).map(toItem),
		{ label: __('Starred'), suffix: '', onTap: () => select(__('Starred')) },
	]
	const customItems = subscribed.value.filter((m) => !m.role).map(toItem)
	const peopleItems = [
		{ label: __('Address Books'), suffix: '', onTap: () => select(__('Address Books')) },
		{ label: __('Contacts'), suffix: '', onTap: () => select(__('Contacts')) },
	]

	const out = [{ label: __('Default'), items: defaultItems }]
	if (customItems.length) out.push({ label: __('Custom'), items: customItems })
	out.push({ label: __('People'), items: peopleItems })
	return out
})

function select(label: string) {
	emit('select', label)
	emit('close')
}

function openSettings() {
	emit('select', __('Settings'))
	emit('close')
}

function toggleAccounts() {
	showAccounts.value = !showAccounts.value
}

function switchAccount(a: UserAccount) {
	store.setAccount(a.id)
	showAccounts.value = false
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
		backdropView.animate({ opacity: 1, duration: 220 })
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
