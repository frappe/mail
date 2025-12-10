<template>
	<Dialog v-model="show" :options="{ title: __('Settings'), size: '4xl' }">
		<template #body>
			<div class="flex" :style="{ height: 'calc(100vh - 9rem)' }">
				<div class="bg-surface-menu-bar flex w-52 shrink-0 flex-col border-r p-4 py-3">
					<h1 class="px-2 text-xl leading-6">{{ __('Settings') }}</h1>
					<div class="mt-3 space-y-1">
						<button
							v-for="tab in tabs"
							:key="tab.label"
							class="flex h-7 w-full items-center gap-2 rounded px-2 py-1"
							:class="[
								activeTab.label == tab.label
									? 'bg-surface-gray-3'
									: 'hover:bg-surface-gray-2',
							]"
							@click="activeTab = tab"
						>
							<component
								:is="tab.icon"
								class="text-ink-gray-6 h-4 w-4 stroke-[1.5]"
							/>
							<span class="text-ink-gray-7 text-base"> {{ tab.label }} </span>
						</button>
					</div>
				</div>
				<div class="flex flex-1 flex-col space-y-5 overflow-y-auto p-12">
					<component :is="activeTab.component" v-if="activeTab" />
				</div>
				<Button
					class="absolute right-0 my-3 mr-4"
					variant="ghost"
					icon="x"
					@click="show = false"
				/>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { computed, inject, markRaw, ref } from 'vue'
import {
	Code,
	DatabaseBackup,
	Feather,
	Fingerprint,
	Mailbox,
	Palette,
	TreePalm,
	User,
} from 'lucide-vue-next'
import { Button, Dialog } from 'frappe-ui'

import AccountSettings from '@/components/Settings/AccountSettings.vue'
import AdvancedSettings from '@/components/Settings/AdvancedSettings.vue'
import AppearanceSettings from '@/components/Settings/AppearanceSettings.vue'
import IdentitySettings from '@/components/Settings/IdentitySettings.vue'
import MailDataExchangeSettings from '@/components/Settings/MailDataExchangeSettings.vue'
import ProfileSettings from '@/components/Settings/ProfileSettings.vue'
import SignatureSettings from '@/components/Settings/SignatureSettings.vue'
import VacationResponseSettings from '@/components/Settings/VacationResponseSettings.vue'

const show = defineModel<boolean>()

const user = inject('$user')

const tabs = computed(() => {
	const allTabs = [
		{
			label: __('Profile'),
			icon: User,
			component: markRaw(ProfileSettings),
		},
		{
			label: __('Account'),
			icon: Mailbox,
			component: markRaw(AccountSettings),
			condition: user.data.is_mail_user,
		},
		{
			label: __('Identity'),
			icon: Fingerprint,
			component: markRaw(IdentitySettings),
			condition: user.data.is_mail_user,
		},
		{
			label: __('Appearance'),
			icon: Palette,
			component: markRaw(AppearanceSettings),
		},
		{
			label: __('Signature'),
			icon: Feather,
			component: markRaw(SignatureSettings),
			condition: user.data.is_mail_user,
		},
		{
			label: __('Vacation Response'),
			icon: TreePalm,
			component: markRaw(VacationResponseSettings),
			condition: user.data.is_mail_user,
		},
		{
			label: __('Mail Data Exchange'),
			icon: DatabaseBackup,
			component: markRaw(MailDataExchangeSettings),
			condition: user.data.is_mail_user && user.data.tenant,
		},
		{
			label: __('Advanced'),
			icon: Code,
			component: markRaw(AdvancedSettings),
			condition: user.data.is_mail_user,
		},
	]
	return allTabs.filter((tab) => tab.condition !== false)
})
const activeTab = ref(tabs.value[0])
</script>
