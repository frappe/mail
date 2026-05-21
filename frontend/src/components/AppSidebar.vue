<template>
	<div
		v-if="isMobile && isSidebarOpen"
		class="fixed inset-0 z-10 bg-black bg-opacity-50"
		@click="closeSidebar"
	/>

	<Transition>
		<Sidebar
			v-if="!isMobile || isSidebarOpen"
			id="sidebar"
			v-model:collapsed="isSidebarCollapsed"
			:header="{
				title,
				subtitle,
				menuItems,
				logo: branding.data?.brand_html || MailLogo,
			}"
			:sections="sidebarItems"
			:class="{ 'fixed left-0 top-0 z-10 w-60': isMobile }"
			:disable-collapse="isMobile"
		>
			<template #footer-items="{ isCollapsed }">
				<QuotaBar v-if="user.data.is_jmap_configured" :is-collapsed />
			</template>
			<template #sidebar-item="{ item }">
				<SidebarItem
					:label="item.label"
					:icon="item.icon"
					:to="item.to"
					:is-active="
						item.activeFor?.includes(
							['Mailbox', 'Mail'].includes(route.name as string)
								? route.params.mailbox
								: route.name,
						)
					"
					:on-click="item.onClick"
					class="group"
				>
					<template #suffix>
						<div class="flex items-center">
							<Dropdown v-if="item.menuOptions" :options="item.menuOptions">
								<Button variant="ghost" class="!bg-transparent" @click.stop>
									<template #icon>
										<Ellipsis
											class="text-ink-gray-6 invisible h-4 w-4 group-hover:visible"
										/>
									</template>
								</Button>
							</Dropdown>
							<span class="text-ink-gray-4 text-sm group-hover:hidden">
								{{ item.suffix }}
							</span>
						</div>
					</template>
				</SidebarItem>
			</template>
		</Sidebar>
	</Transition>

	<SettingsModal v-if="!isMobile" v-model="showSettings" />
	<PWASettings v-else-if="showSettings" @close="showSettings = false" />
	<FolderModal v-model="showFolderModal" :mailbox="selectedMailbox" />
	<DeleteFolderModal v-model="showDeleteMailbox" :mailbox="selectedMailbox" />
	<ShortcutsModal v-model="showShortcuts" />
</template>

<script setup lang="ts">
import { computed, h, inject, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStorage } from '@vueuse/core'
import { Icon } from 'frappe-ui/icons'
import { Check, Keyboard, User } from 'lucide-vue-next'
import { Avatar, Button, Dropdown, Sidebar, SidebarItem, createResource } from 'frappe-ui'

import { FOLDER_ICON_COLOR_MAP } from '@/constants'
import { getIcon, toTitleCase } from '@/utils'
import { useScreenSize, useSidebar } from '@/utils/composables'
import { sessionStore } from '@/stores/session'
import { userStore } from '@/stores/user'
import MailLogo from '@/components/Icons/MailLogo.vue'
import DeleteFolderModal from '@/components/Modals/DeleteFolderModal.vue'
import FolderModal from '@/components/Modals/FolderModal.vue'
import SettingsModal from '@/components/Modals/SettingsModal.vue'
import ShortcutsModal from '@/components/Modals/ShortcutsModal.vue'
import PWASettings from '@/components/PWASettings.vue'
import QuotaBar from '@/components/QuotaBar.vue'

import type { MailboxData } from '@/types'

import BookUser from '~icons/lucide/book-user'
import ContactRound from '~icons/lucide/contact-round'
import Crown from '~icons/lucide/crown'
import Ellipsis from '~icons/lucide/ellipsis'
import Globe from '~icons/lucide/globe'
import LayoutGrid from '~icons/lucide/layout-grid'
import LogOut from '~icons/lucide/log-out'
import Mailbox from '~icons/lucide/mailbox'
import Mails from '~icons/lucide/mails'
import Plus from '~icons/lucide/plus'
import Settings from '~icons/lucide/settings'
import Star from '~icons/lucide/star'
import Trash2 from '~icons/lucide/trash-2'
import Users from '~icons/lucide/users'

const route = useRoute()
const router = useRouter()
const { isMobile } = useScreenSize()
const { isSidebarOpen, closeSidebar } = useSidebar()
const isSidebarCollapsed = useStorage('isSidebarCollapsed', false)
const { logout, branding } = sessionStore()
const store = userStore()
const { mailboxes } = store

const user = inject('$user')

const apps = createResource({
	url: 'mail.api.get_permitted_apps',
	cache: 'otherApps',
	auto: true,
	transform: (data) => data.filter((app) => app.name !== 'mail'),
})

const showSettings = ref(false)
const showFolderModal = ref(false)
const selectedMailbox = ref()
const showDeleteMailbox = ref(false)
const showShortcuts = ref(false)

const title = computed(() =>
	branding.data?.brand_name && branding.data?.brand_name != 'Frappe'
		? branding.data.brand_name
		: 'Mail',
)

const subtitle = computed(() => {
	const currentAccount = user.data.accounts.find((a) => a.name === store.account)
	if (!currentAccount || currentAccount.is_personal) return toTitleCase(user.data.full_name)
	return currentAccount._name
})

const menuItems = computed(() => [
	{
		group: '',
		items: [
			{
				icon: LayoutGrid,
				label: __('Apps'),
				submenu: apps.data?.map?.((app) => ({
					component: h(
						'a',
						{
							class: 'flex items-center gap-2 p-1.5 rounded hover:bg-surface-gray-2',
							href: app.route,
						},
						[
							h('img', { src: app.logo, class: 'size-6' }),
							h('span', { class: 'max-w-18 text-sm w-full truncate' }, app.title),
						],
					),
				})),
				condition: () => !isMobile.value,
			},
			{
				icon: Mailbox,
				label: __('Mailbox'),
				onClick: () => {
					const mailbox = mailboxes.data?.[0]?.id
					if (mailbox)
						router.push({
							name: 'Mailbox',
							params: { accountId: store.accountId, mailbox },
						})
					else
						router.push({
							name: 'AddressBooks',
							params: { accountId: store.accountId },
						})
				},
				condition: () =>
					user.data.is_mail_admin &&
					user.data.is_jmap_configured &&
					route.meta.isDashboard,
			},
			{
				icon: Crown,
				label: __('Admin Dashboard'),
				onClick: () => router.push('/dashboard'),
				condition: () =>
					user.data.is_jmap_configured &&
					user.data.is_mail_admin &&
					!route.meta.isDashboard &&
					!isMobile.value,
			},
		],
	},
	{
		group: '',
		items: [
			{
				icon: Settings,
				label: __('Settings'),
				onClick: () => (showSettings.value = true),
			},
			{
				icon: Keyboard,
				label: __('Shortcuts'),
				onClick: () => (showShortcuts.value = true),
				condition: () => !isMobile.value,
			},
		],
	},
	{
		group: '',
		items: [
			{
				icon: User,
				label: __('Accounts'),
				submenu: user.data.accounts.map?.((a) => ({
					component: h(
						'div',
						{
							class: 'flex items-center gap-2 p-1.5 rounded hover:bg-surface-gray-2 cursor-pointer w-48 shrink-0',
							onClick: async () => {
								router.push({
									name: route.name,
									params: { ...route.params, accountId: a.id },
								})
							},
						},
						[
							h(Avatar, { label: a._name, size: 'md' }),
							h('span', { class: 'text-sm w-full truncate' }, a._name),
							a.id === store.accountId &&
								h(Check, { label: a._name, class: 'shrink-0 icon' }),
						],
					),
				})),
				condition: () => user.data.accounts?.length > 1 && !route.meta.isDashboard,
			},
			{
				icon: LogOut,
				label: __('Log Out'),
				onClick: logout.submit,
			},
		],
	},
])

const dashboardItems = [
	{
		items: [
			{
				label: __('Domains'),
				icon: Globe,
				to: { name: 'Domains' },
				activeFor: ['Domains', 'Domain'],
			},
			{
				label: __('Members'),
				icon: Users,
				to: { name: 'Members' },
				activeFor: ['Members', 'Invites', 'Member'],
			},
			{
				label: __('Mailing Lists'),
				icon: Mails,
				to: { name: 'MailingLists' },
				activeFor: ['MailingLists', 'MailingList'],
			},
		],
	},
]

const mailboxItems = computed(
	() =>
		mailboxes.data
			?.filter((mailbox: MailboxData) => mailbox.subscribed)
			?.map((mailbox: MailboxData) => ({
				label: mailbox._name,
				icon: h(Icon, {
					name: getIcon(mailbox),
					class: FOLDER_ICON_COLOR_MAP[mailbox.color],
				}),
				to: {
					name: 'Mailbox',
					params: { accountId: store.accountId, mailbox: mailbox.id },
				},
				suffix: mailbox.unread_threads ? String(mailbox.unread_threads) : '',
				activeFor: [mailbox.id],
				menuOptions: [
					{
						label: __('Configure'),
						icon: Settings,
						onClick: () => {
							selectedMailbox.value = mailbox
							showFolderModal.value = true
						},
					},
					{
						label: __('Delete'),
						theme: 'red',
						icon: Trash2,
						onClick: () => {
							selectedMailbox.value = mailbox
							showDeleteMailbox.value = true
						},
					},
				],
			})) || [],
)

const sidebarItems = computed(() => {
	if (route.meta.isDashboard) return dashboardItems

	const defaultMailboxes = mailboxItems.value.filter(
		(item) => mailboxes.data?.find((m) => m.id === item.activeFor[0])?.role,
	)
	const starredItem = {
		label: __('Starred'),
		icon: Star,
		to: { name: 'Mailbox', params: { accountId: store.accountId, mailbox: 'starred' } },
		activeFor: ['starred'],
	}
	const defaultItems = [...defaultMailboxes, starredItem]

	const customMailboxes = mailboxItems.value.filter(
		(item) => !mailboxes.data?.find((m) => m.id === item.activeFor[0])?.role,
	)
	const addMailboxItem = {
		label: __('New Folder'),
		icon: Plus,
		onClick: () => {
			selectedMailbox.value = undefined
			showFolderModal.value = true
		},
	}
	const customItems = [...customMailboxes, addMailboxItem]

	const contactsItems = [
		{
			label: __('Address Books'),
			icon: BookUser,
			to: { name: 'AddressBooks', params: { accountId: store.accountId } },
			activeFor: ['AddressBooks', 'AddressBook'],
		},
		{
			label: __('Contacts'),
			icon: ContactRound,
			to: { name: 'Contacts', params: { accountId: store.accountId } },
			activeFor: ['Contacts', 'Contact'],
		},
	]

	return [
		{ label: __('Default'), items: defaultItems },
		{ label: __('Custom'), items: customItems },
		{ label: __('People'), items: contactsItems },
	]
})

// Shortcuts

const handleKeyDown = (event: KeyboardEvent) => {
	if (event.metaKey || event.ctrlKey) {
		if (event.key === ';') {
			event.preventDefault()
			isSidebarCollapsed.value = !isSidebarCollapsed.value
			return
		}
		if (event.key === ',') {
			event.preventDefault()
			showSettings.value = true
		}
	}
}

onMounted(() => window.addEventListener('keydown', handleKeyDown))
onUnmounted(() => window.removeEventListener('keydown', handleKeyDown))
</script>

<style scoped>
.v-enter-from,
.v-leave-to {
	@apply -translate-x-full opacity-0;
}

.v-enter-to,
.v-leave-from {
	@apply translate-x-0 opacity-100;
}
</style>
