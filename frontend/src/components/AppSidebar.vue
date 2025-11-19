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
					:suffix="item.suffix"
					:to="item.to"
					:is-active="
						item.activeFor.includes(
							['Mailbox', 'Mail'].includes(route.name as string)
								? route.params.mailbox
								: route.name,
						)
					"
					:on-click="item.onClick"
				/>
			</template>
		</Sidebar>
	</Transition>
	<SettingsModal v-if="!isMobile" v-model="showSettings" />
	<PWASettings v-else-if="showSettings" @close="showSettings = false" />
</template>

<script setup lang="ts">
import { computed, h, inject, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useStorage } from '@vueuse/core'
import { Sidebar, createResource } from 'frappe-ui'
import SidebarItem from 'frappe-ui/src/components/Sidebar/SidebarItem.vue'

import { toTitleCase } from '@/utils'
import { useScreenSize, useSidebar } from '@/utils/composables'
import { sessionStore } from '@/stores/session'
import { userStore } from '@/stores/user'
import MailLogo from '@/components/Icons/MailLogo.vue'
import QuotaBar from '@/components/QuotaBar.vue'

import AtSign from '~icons/lucide/at-sign'
import Crown from '~icons/lucide/crown'
import Edit3 from '~icons/lucide/edit-3'
import Globe from '~icons/lucide/globe'
import Inbox from '~icons/lucide/inbox'
import LayoutGrid from '~icons/lucide/layout-grid'
import LogOut from '~icons/lucide/log-out'
import MailWarning from '~icons/lucide/mail-warning'
import Mailbox from '~icons/lucide/mailbox'
import Mails from '~icons/lucide/mails'
import Send from '~icons/lucide/send'
import Settings from '~icons/lucide/settings'
import Star from '~icons/lucide/star'
import Tag from '~icons/lucide/tag'
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
				activeFor: ['Members', 'Invites'],
			},
			{
				label: __('Mailing Lists'),
				icon: Mails,
				to: { name: 'MailingLists' },
				activeFor: ['MailingLists', 'MailingList'],
			},
			{
				label: __('Aliases'),
				icon: AtSign,
				to: { name: 'Aliases' },
				activeFor: ['Aliases'],
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
						: Tag,
				to: { name: 'Mailbox', params: { mailbox: mailbox.id } },
				suffix: mailbox.unread_threads ? String(mailbox.unread_threads) : '',
				activeFor: [mailbox.id],
			}),
		) || []

	const starredItem = {
		label: __('Starred'),
		icon: Star,
		to: { name: 'Mailbox', params: { mailbox: 'starred' } },
		activeFor: ['starred'],
	}

	return mailboxes.data?.length
		? [{ items: [mailboxItems[0], starredItem, ...mailboxItems.slice(1)] }]
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
