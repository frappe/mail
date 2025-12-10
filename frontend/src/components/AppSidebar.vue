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
				title:
					branding.data?.brand_name && branding.data?.brand_name != 'Frappe'
						? branding.data.brand_name
						: 'Mail',
				subtitle: toTitleCase(user.data.full_name),
				menuItems,
				logo: branding.data?.brand_html || MailLogo,
			}"
			:sections="sidebarItems"
			:class="{ 'fixed left-0 top-0 z-10 w-60': isMobile }"
			:disable-collapse="isMobile"
		>
			<template #footer-items="{ isCollapsed }">
				<QuotaBar
					v-if="['Mailbox', 'Mail'].includes(route.name as string)"
					:is-collapsed
				/>
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
	<AddMailboxModal v-model="showAddMailbox" />
	<EditMailboxModal v-model="showEditMailbox" :mailbox="selectedMailbox" />
	<DeleteMailboxModal v-model="showDeleteMailbox" :mailbox="selectedMailbox" />
</template>

<script setup lang="ts">
import { computed, h, inject, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStorage } from '@vueuse/core'
import { Button, Dropdown, Sidebar, SidebarItem, createResource } from 'frappe-ui'

import { toTitleCase } from '@/utils'
import { useScreenSize, useSidebar } from '@/utils/composables'
import { sessionStore } from '@/stores/session'
import { userStore } from '@/stores/user'
import MailLogo from '@/components/Icons/MailLogo.vue'
import AddMailboxModal from '@/components/Modals/AddMailboxModal.vue'
import DeleteMailboxModal from '@/components/Modals/DeleteMailboxModal.vue'
import EditMailboxModal from '@/components/Modals/EditMailboxModal.vue'
import SettingsModal from '@/components/Modals/SettingsModal.vue'
import PWASettings from '@/components/PWASettings.vue'
import QuotaBar from '@/components/QuotaBar.vue'

import Archive from '~icons/lucide/archive'
import Bookmark from '~icons/lucide/bookmark'
import Crown from '~icons/lucide/crown'
import Edit3 from '~icons/lucide/edit-3'
import Ellipsis from '~icons/lucide/ellipsis'
import Folder from '~icons/lucide/folder'
import Globe from '~icons/lucide/globe'
import Inbox from '~icons/lucide/inbox'
import LayoutGrid from '~icons/lucide/layout-grid'
import LogOut from '~icons/lucide/log-out'
import MailWarning from '~icons/lucide/mail-warning'
import Mailbox from '~icons/lucide/mailbox'
import Mails from '~icons/lucide/mails'
import Plus from '~icons/lucide/plus'
import Send from '~icons/lucide/send'
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
const { mailboxes } = userStore()

const user = inject('$user')

const apps = createResource({ url: 'mail.api.get_apps', cache: 'otherApps', auto: true })

const showSettings = ref(false)
const showAddMailbox = ref(false)
const selectedMailbox = ref()
const showEditMailbox = ref(false)
const showDeleteMailbox = ref(false)

const menuItems = computed(() => [
	{
		icon: LayoutGrid,
		label: __('Apps'),
		submenu: apps.data?.map?.((app) => ({
			label: app.title,
			icon: app.logo,
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
		condition: () => user.data.is_system_manager && !isMobile.value,
	},
	{
		icon: Mailbox,
		label: __('Mailbox'),
		onClick: () => router.push('/mailbox'),
		condition: () =>
			user.data.is_mail_admin && user.data.default_outgoing && route.meta.isDashboard,
	},
	{
		icon: Crown,
		label: __('Admin Dashboard'),
		onClick: () => router.push('/dashboard'),
		condition: () =>
			user.data.is_mail_admin &&
			user.data.default_outgoing &&
			!route.meta.isDashboard &&
			!isMobile.value,
	},
	{
		icon: Settings,
		label: __('Settings'),
		onClick: () => (showSettings.value = true),
	},
	{
		icon: LogOut,
		label: __('Log Out'),
		onClick: logout.submit,
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

const MAILBOX_ICONS = {
	inbox: Inbox,
	sent: Send,
	trash: Trash2,
	junk: MailWarning,
	drafts: Edit3,
	archive: Archive,
	important: Bookmark,
}

const sidebarItems = computed(() => {
	if (route.meta.isDashboard) return dashboardItems

	const mailboxItems =
		mailboxes.data?.map(
			(mailbox: { id: string; _name: string; role?: string; unread_threads: number }) => ({
				label: mailbox._name,
				icon:
					mailbox.role && mailbox.role in MAILBOX_ICONS
						? MAILBOX_ICONS[mailbox.role as keyof typeof MAILBOX_ICONS]
						: Folder,
				to: { name: 'Mailbox', params: { mailbox: mailbox.id } },
				suffix: mailbox.unread_threads ? String(mailbox.unread_threads) : '',
				activeFor: [mailbox.id],
				menuOptions: [
					{
						label: __('Edit Folder'),
						onClick: () => {
							selectedMailbox.value = mailbox
							showEditMailbox.value = true
						},
					},
					{
						label: __('Delete Folder'),
						onClick: () => {
							selectedMailbox.value = mailbox
							showDeleteMailbox.value = true
						},
					},
				],
			}),
		) || []

	const starredItem = {
		label: __('Starred'),
		icon: Star,
		to: { name: 'Mailbox', params: { mailbox: 'starred' } },
		activeFor: ['starred'],
	}

	const addMailboxItem = {
		label: __('New Folder'),
		icon: Plus,
		onClick: () => (showAddMailbox.value = true),
	}

	return mailboxes.data?.length
		? [{ items: [mailboxItems[0], starredItem, ...mailboxItems.slice(1), addMailboxItem] }]
		: []
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
