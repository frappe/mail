<template>
	<!-- Bottom sheet: scrim + a sheet that slides up. Collapsed when closed so it
	     intercepts no taps. Styling is CSS (iOS ignores inline layout attributes). -->
	<GridLayout :visibility="visible ? 'visible' : 'collapse'" rows="*, auto">
		<StackLayout
			rowSpan="2"
			class="bg-surface-gray-7"
			@loaded="onScrimLoaded"
			@tap="$emit('close')"
		/>

		<!-- @tap absorbs taps on the sheet's blank areas so they don't fall through to
		     the scrim (which closes it); NativeScript routes a tap to the front-most
		     view that has a tap handler. -->
		<StackLayout
			row="1"
			class="bg-surface-white rounded-t-3xl pb-8"
			@loaded="onSheetLoaded"
			@tap="() => {}"
		>
			<StackLayout
				class="bg-surface-gray-3 mb-1 mt-2.5 h-1.5 w-10 rounded-full"
				horizontalAlignment="center"
			/>

			<!-- ── main ── -->
			<StackLayout v-if="view === 'main'">
				<!-- identity -->
				<GridLayout columns="auto, *, auto" class="px-5 pb-4 pt-3.5">
					<UserAvatar
						col="0"
						:size="48"
						:name="current.name || current.email"
						:image="store.user?.user_image ?? ''"
						verticalAlignment="center"
					/>
					<StackLayout col="1" class="ml-3.5" verticalAlignment="center">
						<Label :text="current.name" class="text-lg font-bold" />
						<Label
							:text="current.email"
							class="text-ink-gray-5 text-sm"
							textWrap="false"
						/>
					</StackLayout>
					<GridLayout
						col="2"
						class="h-8 w-8"
						verticalAlignment="center"
						@tap="$emit('close')"
					>
						<Label
							:text="lucide('x')"
							class="font-lucide text-ink-gray-6 text-xl"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
				</GridLayout>

				<!-- current site -->
				<GridLayout
					columns="auto, *, auto"
					class="border-outline-gray-1 bg-surface-gray-1 mx-5 mb-2 rounded-2xl border px-3.5 py-3"
					@tap="view = 'sites'"
				>
					<GridLayout
						col="0"
						class="bg-surface-gray-5 h-9 w-9 rounded-xl"
						verticalAlignment="center"
					>
						<Label
							:text="lucide('globe')"
							class="font-lucide text-xl text-white"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<StackLayout col="1" class="ml-3.5" verticalAlignment="center">
						<Label
							:text="__('SITE')"
							class="text-ink-gray-4 text-xs font-semibold uppercase"
						/>
						<Label
							:text="currentSiteName"
							class="text-base font-semibold"
							textWrap="false"
						/>
					</StackLayout>
					<Label
						col="2"
						:text="lucide('chevron-right')"
						class="font-lucide text-ink-gray-5 text-lg"
						verticalAlignment="center"
					/>
				</GridLayout>

				<!-- accounts -->
				<Label
					:text="__('Accounts')"
					class="text-ink-gray-4 px-5 pb-1 pt-3.5 text-xs font-semibold uppercase"
				/>
				<GridLayout
					v-for="a in accountList"
					:key="a.id"
					columns="auto, *, auto"
					class="px-5 py-3"
					@tap="onSwitchAccount(a)"
				>
					<UserAvatar col="0" :size="40" :name="a.name" verticalAlignment="center" />
					<StackLayout col="1" class="ml-3.5" verticalAlignment="center">
						<Label :text="a.name" class="text-base font-semibold" />
						<Label
							:text="a.subtitle"
							class="text-ink-gray-5 text-sm"
							textWrap="false"
						/>
					</StackLayout>
					<Label
						v-if="a.active"
						col="2"
						:text="lucide('check')"
						class="font-lucide text-lg"
						verticalAlignment="center"
					/>
				</GridLayout>

				<StackLayout class="bg-surface-gray-3 mx-5 my-2 h-px" />

				<StackLayout orientation="horizontal" class="px-5 py-3.5" @tap="onSettings">
					<Label
						:text="lucide('settings')"
						class="font-lucide text-ink-gray-6 text-xl"
						verticalAlignment="center"
					/>
					<Label
						:text="__('Settings')"
						class="ml-3.5 text-base font-semibold"
						verticalAlignment="center"
					/>
				</StackLayout>
				<StackLayout orientation="horizontal" class="px-5 py-3.5" @tap="$emit('logout')">
					<Label
						:text="lucide('log-out')"
						class="font-lucide text-ink-red-3 text-xl"
						verticalAlignment="center"
					/>
					<Label
						:text="__('Sign out')"
						class="text-ink-red-3 ml-3.5 text-base font-semibold"
						verticalAlignment="center"
					/>
				</StackLayout>
			</StackLayout>

			<!-- ── site switcher ── -->
			<StackLayout v-else>
				<GridLayout columns="auto, *" class="px-3.5 pb-2.5 pt-1.5">
					<GridLayout
						col="0"
						class="h-9 w-9"
						verticalAlignment="center"
						@tap="view = 'main'"
					>
						<Label
							:text="lucide('chevron-left')"
							class="font-lucide text-ink-gray-6 text-xl"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<Label
						col="1"
						:text="__('Switch site')"
						class="text-lg font-bold"
						verticalAlignment="center"
					/>
				</GridLayout>
				<GridLayout
					v-for="s in siteList"
					:key="s.url"
					columns="auto, *, auto"
					class="px-5 py-3.5"
					@tap="$emit('switch-site', s.url)"
				>
					<GridLayout
						col="0"
						class="bg-surface-gray-2 h-10 w-10 rounded-2xl"
						verticalAlignment="center"
					>
						<Label
							:text="lucide('globe')"
							class="font-lucide text-ink-gray-6 text-xl"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<StackLayout col="1" class="ml-3.5" verticalAlignment="center">
						<Label :text="s.name" class="text-base font-semibold" />
						<Label :text="s.sub" class="text-ink-gray-5 text-sm" textWrap="false" />
					</StackLayout>
					<Label
						v-if="s.active"
						col="2"
						:text="lucide('check')"
						class="font-lucide text-lg"
						verticalAlignment="center"
					/>
				</GridLayout>

				<StackLayout class="bg-surface-gray-3 mx-5 my-2 h-px" />

				<StackLayout orientation="horizontal" class="px-5 py-3.5" @tap="$emit('add-site')">
					<Label
						:text="lucide('plus')"
						class="font-lucide text-ink-gray-6 text-xl"
						verticalAlignment="center"
					/>
					<Label
						:text="__('Add site')"
						class="ml-3.5 text-base font-semibold"
						verticalAlignment="center"
					/>
				</StackLayout>
			</StackLayout>

			<StackLayout :height="safeBottom" />
		</StackLayout>
	</GridLayout>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { CoreTypes } from '@nativescript/core'

import { lucide } from '@/utils/lucide'
import { safeAreaBottom } from '@/utils/safeArea'
import { siteStore } from '@/stores/site'
import { userStore } from '@/stores/user'
import UserAvatar from '@/components/UserAvatar.vue'

import type { UserAccount } from '@mail/types'
import type { EventData, View } from '@nativescript/core'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
	close: []
	settings: []
	logout: []
	'switch-site': [url: string]
	'add-site': []
}>()

const site = siteStore()
const store = userStore()

const SHEET_OFFSET = 1000 // enough to push the sheet fully below the screen
const safeBottom = safeAreaBottom()
const visible = ref(false)
const view = ref<'main' | 'sites'>('main')

let sheetView: View | null = null
let scrimView: View | null = null

const accounts = computed<UserAccount[]>(() => store.user?.accounts ?? [])

const current = computed(() => ({
	name: store.user?.full_name || store.user?.name || '',
	email: store.user?.email || '',
}))

const accountList = computed(() =>
	accounts.value.map((a) => ({
		id: a.id,
		name: a._name,
		subtitle: a.is_personal ? __('Personal') : __('Group'),
		active: a.id === store.accountId,
	})),
)

const hostOf = (url: string) => url.replace(/^https?:\/\//, '').replace(/\/+$/, '')

const siteList = computed(() =>
	site.sites.map((s) => ({
		url: s.url,
		name: s.app_name || hostOf(s.url),
		sub: hostOf(s.url),
		active: s.url === site.activeSiteUrl,
	})),
)

const currentSiteName = computed(
	() => site.activeSite?.app_name || hostOf(site.activeSite?.url ?? ''),
)

function onSwitchAccount(a: { id: string; active: boolean }) {
	if (!a.active) store.setAccount(a.id)
	emit('close')
}

function onSettings() {
	emit('close')
	emit('settings')
}

function onScrimLoaded(args: EventData) {
	scrimView = args.object as View
	scrimView.opacity = 0
}

function onSheetLoaded(args: EventData) {
	sheetView = args.object as View
	sheetView.translateY = SHEET_OFFSET
}

watch(
	() => props.open,
	(open) => (open ? openSheet() : closeSheet()),
)

function openSheet() {
	view.value = 'main'
	visible.value = true
	nextTick(() => {
		if (!sheetView || !scrimView) return
		sheetView.translateY = SHEET_OFFSET
		scrimView.opacity = 0
		sheetView.animate({
			translate: { x: 0, y: 0 },
			duration: 300,
			curve: CoreTypes.AnimationCurve.cubicBezier(0.22, 1, 0.36, 1),
		})
		scrimView.animate({ opacity: 0.4, duration: 260 })
	})
}

function closeSheet() {
	if (!sheetView || !scrimView) {
		visible.value = false
		return
	}
	Promise.all([
		sheetView.animate({
			translate: { x: 0, y: SHEET_OFFSET },
			duration: 260,
			curve: CoreTypes.AnimationCurve.cubicBezier(0.22, 1, 0.36, 1),
		}),
		scrimView.animate({ opacity: 0, duration: 220 }),
	])
		.catch(() => {})
		.finally(() => (visible.value = false))
}
</script>
