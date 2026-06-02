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
			:backgroundColor="C.surface"
		>
			<!-- Account header -->
			<StackLayout row="0" :marginTop="safeTop">
				<GridLayout columns="auto, *, auto" padding="14 16" verticalAlignment="center">
					<GridLayout
						col="0"
						width="42"
						height="42"
						borderRadius="12"
						:backgroundColor="C.accent"
					>
						<Label
							:text="brandInitial"
							color="#FFFFFF"
							:fontSize="20"
							fontWeight="700"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<StackLayout col="1" marginLeft="12" verticalAlignment="center">
						<Label :text="title" :color="C.text" :fontSize="16.5" fontWeight="700" />
						<Label
							v-if="subtitle"
							:text="subtitle"
							:color="C.text3"
							:fontSize="13.5"
							textWrap="false"
						/>
					</StackLayout>
					<GridLayout
						col="2"
						width="34"
						height="34"
						borderRadius="34"
						:backgroundColor="C.surface3"
						@tap="toggleMenu"
					>
						<Label
							:text="showMenu ? '▴' : '▾'"
							:color="C.text2"
							:fontSize="16"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
				</GridLayout>

				<!-- Account / settings / logout menu (revealed by the chevron) -->
				<StackLayout v-if="showMenu" padding="0 8 6">
					<GridLayout
						v-for="a in accounts"
						:key="a.id"
						columns="*, auto"
						padding="11 14"
						borderRadius="13"
						@tap="switchAccount(a)"
					>
						<Label col="0" :text="a._name" :color="C.text" :fontSize="15.5" />
						<Label
							v-if="a.id === store.accountId"
							col="1"
							text="✓"
							:color="C.accent"
							:fontSize="15.5"
						/>
					</GridLayout>
					<StackLayout padding="11 14" borderRadius="13" @tap="openSettings">
						<Label :text="__('Settings')" :color="C.text" :fontSize="15.5" />
					</StackLayout>
					<StackLayout padding="11 14" borderRadius="13" @tap="$emit('logout')">
						<Label :text="__('Log out')" color="#E03636" :fontSize="15.5" />
					</StackLayout>
				</StackLayout>
			</StackLayout>

			<!-- Folder sections -->
			<ScrollView row="1">
				<StackLayout padding="0 8">
					<template v-for="section in sections" :key="section.label">
						<Label
							:text="section.label"
							:color="C.text4"
							:fontSize="12"
							fontWeight="600"
							textTransform="uppercase"
							padding="16 16 7"
						/>
						<GridLayout
							v-for="item in section.items"
							:key="item.label"
							columns="*, auto"
							padding="11 14"
							borderRadius="13"
							:backgroundColor="item.label === activeLabel ? C.sel : 'transparent'"
							@tap="item.onTap"
						>
							<Label
								col="0"
								:text="item.label"
								:color="C.text"
								:fontSize="15.5"
								:fontWeight="item.label === activeLabel ? '700' : '500'"
							/>
							<Label
								v-if="item.suffix"
								col="1"
								:text="item.suffix"
								:color="C.text3"
								:fontSize="13"
								fontWeight="500"
								verticalAlignment="center"
							/>
						</GridLayout>

						<!-- New Folder action under the Custom section -->
						<StackLayout
							v-if="section.label === customLabel"
							padding="11 14"
							borderRadius="13"
							@tap="$emit('select', customLabel)"
						>
							<Label
								:text="__('New Folder')"
								:color="C.text3"
								:fontSize="15.5"
								fontWeight="500"
							/>
						</StackLayout>
					</template>
					<StackLayout height="12" />
				</StackLayout>
			</ScrollView>

			<!-- Storage meter -->
			<StackLayout
				row="2"
				:marginBottom="safeBottom"
				padding="14 18 18"
				borderTopWidth="1"
				:borderTopColor="C.border"
			>
				<Label
					:text="__('Storage')"
					:color="C.text"
					:fontSize="15"
					fontWeight="600"
					marginBottom="10"
				/>
				<GridLayout height="6" borderRadius="6" :backgroundColor="C.surface3">
					<StackLayout
						:width="storagePercent + '%'"
						height="6"
						borderRadius="6"
						horizontalAlignment="left"
						:backgroundColor="C.accent"
					/>
				</GridLayout>
				<Label :text="storageLabel" :color="C.text3" :fontSize="12.5" marginTop="8" />
			</StackLayout>
		</GridLayout>
	</GridLayout>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { CoreTypes } from '@nativescript/core'

import { safeAreaBottom, safeAreaTop } from '@/utils/safeArea'
import { siteStore } from '@/stores/site'
import { userStore } from '@/stores/user'

import type { MailboxData, UserAccount } from '@mail/types'
import type { EventData, View } from '@nativescript/core'

const props = defineProps<{ open: boolean; activeLabel: string }>()
const emit = defineEmits<{ close: []; select: [label: string]; logout: [] }>()

const site = siteStore()
const store = userStore()

// Design tokens (espresso, light theme) — see the Claude Design handoff.
const C = {
	text: '#171717',
	text2: '#525252',
	text3: '#7C7C7C',
	text4: '#A3A3A3',
	border: '#EDEDED',
	surface: '#FFFFFF',
	surface3: '#F1F1F1',
	accent: '#0466DC',
	sel: 'rgba(0, 0, 0, 0.05)',
}

const PANEL_WIDTH = 300
const customLabel = __('Custom')

const visible = ref(false)
const showMenu = ref(false)
const safeTop = safeAreaTop()
const safeBottom = safeAreaBottom()

// Native views captured on @loaded so we can animate the slide/fade directly.
let panelView: View | null = null
let backdropView: View | null = null

const title = computed(() => site.activeSite?.app_name || 'Mail')
const brandInitial = computed(() => (title.value[0] || 'M').toUpperCase())
const accounts = computed<UserAccount[]>(() => store.user?.accounts ?? [])
const subtitle = computed(() => {
	const current = accounts.value.find((a) => a.id === store.accountId)
	return current?._name || store.user?.full_name || ''
})

// Storage meter — placeholder until a mobile storage API is wired.
const storagePercent = 4.63
const storageLabel = computed(() => `${storagePercent}% ${__('of 10 GB used')}`)

const subscribed = computed(() => store.mailboxes.filter((m) => m.subscribed))
const mailboxSuffix = (m: MailboxData) =>
	m.unread_threads ? m.unread_threads.toLocaleString() : ''

// Default (role mailboxes + Starred), Custom (user folders), People.
const sections = computed(() => {
	const toItem = (m: MailboxData) => ({
		label: m._name,
		suffix: mailboxSuffix(m),
		onTap: () => select(m._name),
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

function openSettings() {
	emit('select', __('Settings'))
	emit('close')
}

function toggleMenu() {
	showMenu.value = !showMenu.value
}

function switchAccount(a: UserAccount) {
	store.setAccount(a.id)
	showMenu.value = false
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
