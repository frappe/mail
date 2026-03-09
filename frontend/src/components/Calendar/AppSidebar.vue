<script setup lang="ts">
import { computed, h, inject } from 'vue'
import { LayoutGrid, LogOut } from 'lucide-vue-next'
import { SidebarHeader, createResource } from 'frappe-ui'

import { toTitleCase } from '@/utils'
import { sessionStore } from '@/stores/session'
import CalendarLogo from '@/components/Icons/CalendarLogo.vue'

const { branding, logout } = sessionStore()

const user = inject('$user')

const title = computed(() =>
	branding.data?.brand_name && branding.data?.brand_name != 'Frappe'
		? branding.data.brand_name
		: 'Calendar',
)

const apps = createResource({ url: 'mail.api.get_apps', cache: 'otherApps', auto: true })

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
		condition: () => user.data.is_system_manager,
	},
	{
		icon: LogOut,
		label: __('Log Out'),
		onClick: logout.submit,
	},
])
</script>

<template>
	<div
		class="border-outline-gray-1 bg-surface-menu-bar flex h-full flex-shrink-0 flex-col overflow-y-auto overflow-x-hidden border-r p-2 transition-all duration-300 ease-in-out"
	>
		<SidebarHeader
			:title="title"
			:subtitle="toTitleCase(user.data.full_name)"
			:logo="branding.data?.brand_html || CalendarLogo"
			:menu-items
		>
			<template #logo>
				<slot name="header-logo"></slot>
			</template>
		</SidebarHeader>
	</div>
</template>
