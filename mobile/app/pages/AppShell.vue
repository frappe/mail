<template>
	<Page actionBarHidden="true">
		<!-- Root single-cell grid so the drawer overlays the whole screen. -->
		<GridLayout>
			<GridLayout rows="auto, *">
				<!-- Top bar (pushed below the Android status bar / camera cutout) -->
				<GridLayout
					row="0"
					:marginTop="safeTop"
					columns="auto, *"
					class="border-b px-2 py-3"
				>
					<Label col="0" text="☰" class="px-3 text-2xl" @tap="drawerOpen = true" />
					<Label
						col="1"
						:text="currentView || title"
						verticalAlignment="center"
						class="text-lg font-semibold"
					/>
				</GridLayout>

				<!-- Placeholder content area (real thread list lands in a later issue) -->
				<StackLayout
					row="1"
					verticalAlignment="center"
					horizontalAlignment="center"
					class="p-6"
				>
					<Label
						:text="currentView || __('Loading…')"
						class="mb-1 text-2xl font-bold"
						textAlignment="center"
					/>
					<Label
						:text="__('Thread list coming soon')"
						class="text-ink-gray-5 text-base"
						textAlignment="center"
					/>
				</StackLayout>
			</GridLayout>

			<NavDrawer
				:open="drawerOpen"
				:active-label="currentView"
				@close="drawerOpen = false"
				@select="onSelect"
				@open-account="sheetOpen = true"
			/>

			<AccountSheet
				:open="sheetOpen"
				@close="sheetOpen = false"
				@settings="onSettings"
				@logout="logout"
				@switch-site="onSwitchSite"
				@add-site="onAddSite"
			/>
		</GridLayout>
	</Page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { $navigateTo } from 'nativescript-vue'

import { safeAreaTop } from '@/utils/safeArea'
import { loadTranslations } from '@/utils/translation'
import { sessionStore } from '@/stores/session'
import { siteStore } from '@/stores/site'
import { userStore } from '@/stores/user'
import LandingPage from '@/pages/LandingPage.vue'
import AccountSheet from '@/components/AccountSheet.vue'
import NavDrawer from '@/components/NavDrawer.vue'

const site = siteStore()
const session = sessionStore()
const store = userStore()

const drawerOpen = ref(false)
const sheetOpen = ref(false)
const currentView = ref('')
const safeTop = safeAreaTop()

const title = computed(() => site.activeSite?.app_name || 'Mail')

onMounted(() => {
	void store.fetchUser()
})

// Default the content to the Inbox (or first role mailbox) once mailboxes load.
watch(
	() => store.mailboxes,
	(mailboxes) => {
		if (currentView.value || !mailboxes.length) return
		const inbox = mailboxes.find((m) => m.role === 'inbox') ?? mailboxes.find((m) => m.role)
		if (inbox) currentView.value = inbox._name
	},
	{ immediate: true },
)

function onSelect(label: string) {
	currentView.value = label
}

function onSettings() {
	drawerOpen.value = false
	currentView.value = __('Settings')
}

function logout() {
	if (!site.activeSite) return
	session.logout(site.activeSite.url)
	store.reset()
	void loadTranslations()
	$navigateTo(LandingPage, { clearHistory: true })
}

// Switch the active site: load its stored session and reload user data, or fall
// back to the landing page when that site isn't signed in.
function onSwitchSite(url: string) {
	sheetOpen.value = false
	drawerOpen.value = false
	site.setActiveSite(url)
	session.load(url)
	if (session.isLoggedIn) {
		store.reset()
		currentView.value = ''
		void store.fetchUser()
		void loadTranslations()
	} else {
		$navigateTo(LandingPage, { clearHistory: true })
	}
}

function onAddSite() {
	sheetOpen.value = false
	drawerOpen.value = false
	$navigateTo(LandingPage, { clearHistory: true })
}
</script>
