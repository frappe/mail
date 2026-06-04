<template>
	<Page actionBarHidden="true">
		<!-- Root single-cell grid so the drawer / sheet / toast overlay everything. -->
		<GridLayout>
			<!-- Thread list for the selected mailbox … -->
			<MailboxScreen
				v-if="activeMailbox"
				:mailbox="activeMailbox"
				@open-drawer="drawerOpen = true"
				@open-thread="openThread"
			/>

			<!-- … or a placeholder for non-mailbox views (Settings, Address Books, Contacts). -->
			<GridLayout v-else rows="auto, *" class="bg-surface-white">
				<GridLayout row="0" columns="auto, *" class="px-1 py-2" :marginTop="safeTop">
					<GridLayout col="0" class="h-10 w-10" @tap="drawerOpen = true">
						<Label
							:text="lucide('menu')"
							class="font-lucide text-ink-gray-7 text-2xl"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<Label
						col="1"
						:text="currentView || title"
						class="text-ink-gray-9 ml-1 text-2xl font-bold"
						verticalAlignment="center"
					/>
				</GridLayout>
				<StackLayout
					row="1"
					verticalAlignment="center"
					horizontalAlignment="center"
					class="p-6"
				>
					<Label
						:text="currentView || __('Loading…')"
						class="text-ink-gray-8 mb-1 text-2xl font-bold"
						textAlignment="center"
					/>
					<Label
						:text="__('Coming soon')"
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

			<!-- Toast: brief feedback for placeholder actions (search/compose/filter). -->
			<Label
				v-if="toast"
				:text="toast"
				class="bg-surface-gray-7 rounded-full px-5 py-3 text-base font-semibold text-white"
				horizontalAlignment="center"
				verticalAlignment="bottom"
				marginBottom="120"
				textWrap="false"
			/>
		</GridLayout>
	</Page>
</template>

<script setup lang="ts">
import { computed, onMounted, provide, ref, watch } from 'vue'
import { $navigateTo } from 'nativescript-vue'

import { lucide } from '@/utils/lucide'
import { safeAreaTop } from '@/utils/safeArea'
import { loadTranslations } from '@/utils/translation'
import { sessionStore } from '@/stores/session'
import { siteStore } from '@/stores/site'
import { userStore } from '@/stores/user'
import LandingPage from '@/pages/LandingPage.vue'
import ThreadView from '@/pages/ThreadView.vue'
import AccountSheet from '@/components/AccountSheet.vue'
import MailboxScreen from '@/components/MailboxScreen.vue'
import NavDrawer from '@/components/NavDrawer.vue'

import type { ActiveMailbox, NavSelection } from '@/types/navigation'
import type { MailboxData, Thread } from '@mail/types'

const site = siteStore()
const session = sessionStore()
const store = userStore()

const drawerOpen = ref(false)
const sheetOpen = ref(false)
const currentView = ref('')
const activeMailbox = ref<ActiveMailbox | null>(null)
const safeTop = safeAreaTop()

const title = computed(() => site.activeSite?.app_name || 'Mail')

// Toast (provided to descendants as `flash`) — see MailboxScreen placeholders.
const toast = ref<string | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null
function flash(msg: string) {
	toast.value = msg
	if (toastTimer) clearTimeout(toastTimer)
	toastTimer = setTimeout(() => (toast.value = null), 1800)
}
provide('flash', flash)

onMounted(() => {
	void store.fetchUser()
})

const toActiveMailbox = (m: MailboxData): ActiveMailbox => ({
	id: m.id,
	label: m._name,
	role: m.role,
	total: m.total_threads,
})

// Default the content to the Inbox (or first role mailbox) once mailboxes load.
watch(
	() => store.mailboxes,
	(mailboxes) => {
		if (currentView.value || !mailboxes.length) return
		const inbox = mailboxes.find((m) => m.role === 'inbox') ?? mailboxes.find((m) => m.role)
		if (inbox) {
			activeMailbox.value = toActiveMailbox(inbox)
			currentView.value = inbox._name
		}
	},
	{ immediate: true },
)

function onSelect(selection: NavSelection) {
	if (selection.kind === 'mailbox') {
		activeMailbox.value = toActiveMailbox(selection.mailbox)
		currentView.value = selection.mailbox._name
	} else if (selection.kind === 'starred') {
		activeMailbox.value = { id: 'starred', label: __('Starred'), role: 'starred', total: null }
		currentView.value = __('Starred')
	} else {
		activeMailbox.value = null
		currentView.value = selection.label
	}
}

function openThread(thread: Thread) {
	$navigateTo(ThreadView, { props: { thread } })
}

function onSettings() {
	drawerOpen.value = false
	activeMailbox.value = null
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
		activeMailbox.value = null
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
