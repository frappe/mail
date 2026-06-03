<template>
	<!-- Bottom sheet: scrim + a sheet that slides up. Collapsed when closed so it
	     intercepts no taps. Styling is CSS (iOS ignores inline layout attributes). -->
	<GridLayout :visibility="visible ? 'visible' : 'collapse'" rows="*, auto">
		<StackLayout rowSpan="2" class="as-scrim" @loaded="onScrimLoaded" @tap="$emit('close')" />

		<StackLayout row="1" class="as-sheet" @loaded="onSheetLoaded">
			<StackLayout class="as-handle" horizontalAlignment="center" />

			<!-- ── main ── -->
			<StackLayout v-if="view === 'main'">
				<!-- identity -->
				<GridLayout columns="auto, *, auto" class="as-identity">
					<GridLayout col="0" class="as-avatar-lg" verticalAlignment="center">
						<Image
							v-if="current.image"
							:src="current.image"
							stretch="aspectFill"
							class="as-avatar-img-lg"
						/>
						<Label
							v-else
							:text="current.initials"
							class="as-avatar-label-lg"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<StackLayout col="1" class="as-gap" verticalAlignment="center">
						<Label :text="current.name" class="as-id-name" />
						<Label :text="current.email" class="as-id-email" textWrap="false" />
					</StackLayout>
					<GridLayout
						col="2"
						class="as-close"
						verticalAlignment="center"
						@tap="$emit('close')"
					>
						<Label
							:text="lucide('x')"
							class="as-close-icon"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
				</GridLayout>

				<!-- current site -->
				<GridLayout columns="auto, *, auto" class="as-site-pill" @tap="view = 'sites'">
					<GridLayout col="0" class="as-site-badge" verticalAlignment="center">
						<Label
							:text="lucide('globe')"
							class="as-site-badge-glyph"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<StackLayout col="1" class="as-gap" verticalAlignment="center">
						<Label :text="__('SITE')" class="as-site-kicker" />
						<Label :text="currentSiteName" class="as-site-name" textWrap="false" />
					</StackLayout>
					<Label
						col="2"
						:text="lucide('chevron-right')"
						class="as-chev"
						verticalAlignment="center"
					/>
				</GridLayout>

				<!-- accounts -->
				<Label :text="__('Accounts')" class="as-section" />
				<GridLayout
					v-for="a in accountList"
					:key="a.id"
					columns="auto, *, auto"
					class="as-acct"
					@tap="onSwitchAccount(a)"
				>
					<GridLayout col="0" class="as-avatar" verticalAlignment="center">
						<Label
							:text="a.initials"
							class="as-avatar-label"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<StackLayout col="1" class="as-gap" verticalAlignment="center">
						<Label :text="a.name" class="as-acct-name" />
						<Label :text="a.subtitle" class="as-acct-email" textWrap="false" />
					</StackLayout>
					<Label
						v-if="a.active"
						col="2"
						:text="lucide('check')"
						class="as-check"
						verticalAlignment="center"
					/>
				</GridLayout>

				<StackLayout class="as-divider" />

				<StackLayout orientation="horizontal" class="as-row" @tap="onSettings">
					<Label
						:text="lucide('settings')"
						class="as-row-icon"
						verticalAlignment="center"
					/>
					<Label
						:text="__('Settings')"
						class="as-row-label"
						verticalAlignment="center"
					/>
				</StackLayout>
				<StackLayout orientation="horizontal" class="as-row" @tap="$emit('logout')">
					<Label
						:text="lucide('log-out')"
						class="as-row-icon as-danger"
						verticalAlignment="center"
					/>
					<Label
						:text="__('Sign out')"
						class="as-row-label as-danger"
						verticalAlignment="center"
					/>
				</StackLayout>
			</StackLayout>

			<!-- ── site switcher ── -->
			<StackLayout v-else>
				<GridLayout columns="auto, *" class="as-sites-head">
					<GridLayout
						col="0"
						class="as-back"
						verticalAlignment="center"
						@tap="view = 'main'"
					>
						<Label
							:text="lucide('chevron-left')"
							class="as-back-icon"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<Label
						col="1"
						:text="__('Switch site')"
						class="as-sites-title"
						verticalAlignment="center"
					/>
				</GridLayout>
				<GridLayout
					v-for="s in siteList"
					:key="s.url"
					columns="auto, *, auto"
					class="as-siterow"
					@tap="$emit('switch-site', s.url)"
				>
					<GridLayout col="0" class="as-site-sq" verticalAlignment="center">
						<Label
							:text="lucide('globe')"
							class="as-site-sq-glyph"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<StackLayout col="1" class="as-gap" verticalAlignment="center">
						<Label :text="s.name" class="as-acct-name" />
						<Label :text="s.sub" class="as-acct-email" textWrap="false" />
					</StackLayout>
					<Label
						v-if="s.active"
						col="2"
						:text="lucide('check')"
						class="as-check"
						verticalAlignment="center"
					/>
				</GridLayout>

				<StackLayout class="as-divider" />

				<StackLayout orientation="horizontal" class="as-row" @tap="$emit('add-site')">
					<Label
						:text="lucide('plus')"
						class="as-row-icon as-accent"
						verticalAlignment="center"
					/>
					<Label
						:text="__('Add site')"
						class="as-row-label"
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

function initials(name: string): string {
	return (
		name
			.split(/\s+/)
			.map((w) => w[0])
			.slice(0, 2)
			.join('')
			.toUpperCase() || '?'
	)
}

function resolveImage(image?: string | null): string {
	if (!image) return ''
	if (/^(https?:|data:|file:|~\/)/i.test(image)) return image
	if (image.startsWith('/')) return `${site.activeSite?.url ?? ''}${image}`
	return image
}

const accounts = computed<UserAccount[]>(() => store.user?.accounts ?? [])

const current = computed(() => {
	const name = store.user?.full_name || store.user?.name || ''
	const email = store.user?.email || ''
	return {
		name,
		email,
		image: resolveImage(store.user?.user_image),
		initials: initials(name || email),
	}
})

const accountList = computed(() =>
	accounts.value.map((a) => ({
		id: a.id,
		name: a._name,
		subtitle: a.is_personal ? __('Personal') : __('Group'),
		initials: initials(a._name),
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
		scrimView.animate({ opacity: 1, duration: 260 })
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

<!-- Design tokens (espresso, light) from the Claude Design account-sheet handoff. -->
<style scoped>
.as-scrim {
	background-color: rgba(0, 0, 0, 0.4);
}
.as-sheet {
	background-color: #ffffff;
	border-top-left-radius: 24;
	border-top-right-radius: 24;
	padding-bottom: 30;
}
.as-handle {
	width: 38;
	height: 5;
	border-radius: 5;
	background-color: #dadada;
	margin: 10 0 4 0;
}

/* identity */
.as-identity {
	padding: 14 20 16;
}
.as-gap {
	margin-left: 14;
}
.as-id-name {
	color: #171717;
	font-size: 17;
	font-weight: 700;
}
.as-id-email {
	color: #7c7c7c;
	font-size: 13.5;
}
.as-close {
	width: 32;
	height: 32;
}
.as-close-icon {
	font-family: 'lucide';
	color: #525252;
	font-size: 19;
}

/* avatars */
.as-avatar,
.as-avatar-lg {
	border-radius: 52;
	background-color: #f1f1f1;
}
.as-avatar {
	width: 40;
	height: 40;
}
.as-avatar-lg {
	width: 52;
	height: 52;
}
.as-avatar-img-lg {
	width: 52;
	height: 52;
	border-radius: 52;
}
.as-avatar-label {
	color: #525252;
	font-size: 14;
	font-weight: 600;
}
.as-avatar-label-lg {
	color: #525252;
	font-size: 18;
	font-weight: 600;
}

/* site pill */
.as-site-pill {
	margin: 0 20 8 20;
	padding: 12 14;
	border-radius: 14;
	border-width: 1;
	border-color: #ededed;
	background-color: #f8f8f8;
}
.as-site-badge {
	width: 34;
	height: 34;
	border-radius: 10;
	background-color: #525252;
}
.as-site-badge-glyph {
	font-family: 'lucide';
	color: #ffffff;
	font-size: 20;
}
.as-site-kicker {
	color: #a3a3a3;
	font-size: 11.5;
	font-weight: 600;
	text-transform: uppercase;
}
.as-site-name {
	color: #171717;
	font-size: 15;
	font-weight: 600;
}
.as-chev {
	font-family: 'lucide';
	color: #7c7c7c;
	font-size: 18;
}

/* section + account rows */
.as-section {
	color: #a3a3a3;
	font-size: 12;
	font-weight: 600;
	text-transform: uppercase;
	padding: 14 20 4;
}
.as-acct {
	padding: 11 20;
	background-color: transparent;
}
.as-acct-name {
	color: #171717;
	font-size: 15.5;
	font-weight: 600;
}
.as-acct-email {
	color: #7c7c7c;
	font-size: 13;
}
.as-check {
	font-family: 'lucide';
	color: #171717;
	font-size: 18;
}

/* generic action rows */
.as-row {
	padding: 13 20;
}
.as-row-icon {
	font-family: 'lucide';
	color: #525252;
	font-size: 21;
}
.as-row-label {
	color: #171717;
	font-size: 15.5;
	font-weight: 600;
	margin-left: 14;
}
.as-accent {
	color: #525252;
}
.as-danger {
	color: #e03636;
}
.as-divider {
	height: 1;
	background-color: #ededed;
	margin: 8 20;
}

/* site switcher */
.as-sites-head {
	padding: 6 14 10;
}
.as-back {
	width: 36;
	height: 36;
	border-radius: 36;
}
.as-back-icon {
	font-family: 'lucide';
	color: #525252;
	font-size: 22;
}
.as-sites-title {
	color: #171717;
	font-size: 17;
	font-weight: 700;
}
.as-siterow {
	padding: 13 20;
}
.as-site-sq {
	width: 40;
	height: 40;
	border-radius: 12;
	background-color: #f1f1f1;
}
.as-site-sq-glyph {
	font-family: 'lucide';
	color: #525252;
	font-size: 20;
}
</style>
