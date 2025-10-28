<template>
	<div
		v-if="isMobile && isSidebarOpen"
		class="fixed inset-0 z-10 bg-black bg-opacity-50"
		@click="closeSidebar"
	/>

	<Transition>
		<div
			v-if="!isMobile || isSidebarOpen"
			class="bg-surface-menu-bar flex h-full flex-col justify-between border-r duration-300 ease-in-out"
			:class="[
				isSidebarCollapsed && !isMobile ? 'w-14' : 'w-56',
				{ 'fixed left-0 top-0 z-10 shadow-lg': isMobile },
			]"
		>
			<div
				class="flex flex-col overflow-hidden"
				:class="{ 'items-center': isSidebarCollapsed && !isMobile }"
			>
				<UserDropdown class="p-2" :is-collapsed="isSidebarCollapsed && !isMobile" />
				<div class="flex flex-col">
					<SidebarLink
						v-for="link in sidebarLinks"
						:key="link.label"
						:link="link"
						:is-collapsed="isSidebarCollapsed && !isMobile"
						class="mx-2 my-0.5"
					/>
				</div>
			</div>
			<SidebarLink
				v-if="!isMobile"
				:link="{ label: isSidebarCollapsed ? 'Expand' : 'Collapse' }"
				:is-collapsed="isSidebarCollapsed"
				class="m-2"
				@click="isSidebarCollapsed = !isSidebarCollapsed"
			>
				<template #icon>
					<span class="grid h-5 w-6 flex-shrink-0 place-items-center">
						<ArrowLeftFromLine
							class="text-ink-gray-6 h-4 w-4 duration-300 ease-in-out"
							:class="{
								'[transform:rotateY(180deg)]': isSidebarCollapsed,
							}"
						/>
					</span>
				</template>
			</SidebarLink>
		</div>
	</Transition>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useStorage } from '@vueuse/core'
import { ArrowLeftFromLine } from 'lucide-vue-next'

import { useScreenSize, useSidebar } from '@/utils/composables'
import { userStore } from '@/stores/user'
import SidebarLink from '@/components/SidebarLink.vue'
import UserDropdown from '@/components/UserDropdown.vue'

const route = useRoute()
const { isMobile } = useScreenSize()
const { isSidebarOpen, closeSidebar } = useSidebar()
const isSidebarCollapsed = useStorage('sidebar_is_collapsed', false)
const { mailboxes } = userStore()

const dashboardItems = [
	{
		label: __('Domains'),
		icon: 'Globe',
		to: { name: 'Domains' },
		activeFor: ['Domains', 'Domain'],
		forDashboard: true,
	},
	{
		label: __('Members'),
		icon: 'Users',
		to: { name: 'Members' },
		activeFor: ['Members', 'Invites'],
		forDashboard: true,
	},
	{
		label: __('Mailing Lists'),
		icon: 'Mails',
		to: { name: 'MailingLists' },
		activeFor: ['MailingLists', 'MailingList'],
		forDashboard: true,
	},
	{
		label: __('Aliases'),
		icon: 'AtSign',
		to: { name: 'Aliases' },
		activeFor: ['Aliases'],
		forDashboard: true,
	},
]

const MAILBOX_ICONS = {
	inbox: 'Inbox',
	sent: 'Send',
	trash: 'Trash2',
	junk: 'MailWarning',
	drafts: 'Edit3',
}

const sidebarLinks = computed(() => {
	if (route.meta.isDashboard) return dashboardItems

	const mailboxItems =
		mailboxes.data?.map(
			(mailbox: { id: string; _name: string; role?: string; unread_threads: number }) => ({
				label: mailbox._name,
				icon:
					mailbox.role && mailbox.role in MAILBOX_ICONS
						? MAILBOX_ICONS[mailbox.role as keyof typeof MAILBOX_ICONS]
						: 'Tag',
				to: { name: 'Mailbox', params: { mailbox: mailbox.id } },
				count: mailbox.unread_threads,
				activeFor: [mailbox.id],
			}),
		) || []

	const starredItem = {
		label: __('Starred'),
		icon: 'Star',
		to: { name: 'Mailbox', params: { mailbox: 'starred' } },
		activeFor: ['starred'],
	}

	return mailboxes.data?.length ? [mailboxItems[0], starredItem, ...mailboxItems.slice(1)] : []
})

// Shortcuts

const handleKeyDown = (event: KeyboardEvent) => {
	if ((event.metaKey || event.ctrlKey) && event.key === ';') {
		event.preventDefault()
		isSidebarCollapsed.value = !isSidebarCollapsed.value
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
