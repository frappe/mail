<template>
	<div>
		<Dropdown :options="userDropdownOptions">
			<template #default="{ open }">
				<button
					class="flex h-12 items-center rounded-md py-2 duration-300 ease-in-out"
					:class="
						isCollapsed
							? 'w-auto px-0'
							: open
								? 'bg-surface-white w-52 px-2 shadow-sm'
								: 'hover:bg-surface-gray-3 w-52 px-2'
					"
				>
					<span
						v-if="branding.data?.brand_html"
						class="h-8 w-8 flex-shrink-0 rounded"
						v-html="branding.data?.brand_html"
					/>
					<MailLogo v-else class="h-8 w-8 flex-shrink-0 rounded" />
					<div
						class="flex flex-1 flex-col text-left duration-300 ease-in-out"
						:class="
							isCollapsed
								? 'ml-0 w-0 overflow-hidden opacity-0'
								: 'ml-2 w-auto opacity-100'
						"
					>
						<div class="text-base font-medium leading-none">
							<span
								v-if="
									branding.data?.brand_name &&
									branding.data?.brand_name != 'Frappe'
								"
							>
								{{ branding.data?.brand_name }}
							</span>
							<span v-else> Mail </span>
						</div>
						<div class="text-ink-gray-6 mt-1 text-sm leading-none">
							{{ convertToTitleCase(user.data.full_name) }}
						</div>
					</div>
					<div
						class="duration-300 ease-in-out"
						:class="
							isCollapsed
								? 'ml-0 w-0 overflow-hidden opacity-0'
								: 'ml-2 w-auto opacity-100'
						"
					>
						<ChevronDown class="text-ink-gray-6 h-4 w-4" />
					</div>
				</button>
			</template>
		</Dropdown>
		<SettingsModal v-if="!isMobile" v-model="showSettings" />
		<PWASettings v-else-if="showSettings" @close="closeSidebar" />
	</div>
</template>

<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronDown, Crown, LogOut, Mailbox, Settings as SettingsIcon } from 'lucide-vue-next'
import { Dropdown } from 'frappe-ui'

import { convertToTitleCase } from '@/utils'
import { useScreenSize, useSidebar } from '@/utils/composables'
import { sessionStore } from '@/stores/session'
import AppsMenu from '@/components/AppsMenu.vue'
import MailLogo from '@/components/Icons/MailLogo.vue'
import SettingsModal from '@/components/Modals/SettingsModal.vue'
import PWASettings from '@/components/PWASettings.vue'

const user = inject('$user')
const route = useRoute()
const router = useRouter()
const { logout, branding } = sessionStore()
const { isMobile } = useScreenSize()
const { closeSidebar } = useSidebar()

const showSettings = ref(false)

defineProps<{ isCollapsed?: boolean }>()

const userDropdownOptions = [
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
		icon: SettingsIcon,
		label: __('Settings'),
		onClick: () => (showSettings.value = true),
		condition: () => !user.data.is_tenant_owner,
	},
	{
		component: AppsMenu,
		condition: () => user.data.is_system_manager && !isMobile.value,
	},
	{
		icon: LogOut,
		label: __('Log Out'),
		onClick: logout.submit,
	},
]

// Shortcuts

const handleKeyDown = (e: KeyboardEvent) => {
	if ((e.metaKey || e.ctrlKey) && e.key === ',') {
		e.preventDefault()
		showSettings.value = true
	}
}

onMounted(() => window.addEventListener('keydown', handleKeyDown))
onUnmounted(() => window.removeEventListener('keydown', handleKeyDown))
</script>
