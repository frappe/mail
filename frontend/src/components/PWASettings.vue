<template>
	<div class="bg-surface-white fixed inset-0 z-10 flex flex-col">
		<div class="sticky top-0 flex items-center border-b px-3 py-2.5">
			<Button variant="ghost" class="mr-2" @click="emit('close')">
				<template #icon>
					<ChevronLeft class="text-ink-gray-5 h-4 w-4" />
				</template>
			</Button>

			<h2 class="font-semibold leading-5">{{ __('Settings') }}</h2>
		</div>

		<div class="px-3 py-4">
			<Switch
				size="md"
				:label="__('Enable Push Notifications')"
				:class="{ 'p-2': description }"
				:model-value="isPushNotificationsEnabled"
				:disabled="!hasPushRelayServer || isLoading"
				:description
				@update:model-value="togglePushNotifications"
			/>

			<div v-if="isLoading" class="-mt-2 flex items-center justify-center gap-2">
				<LoadingIndicator class="text-ink-gray-7 h-3 w-3" />
				<span class="text-sm">
					{{
						isPushNotificationsEnabled
							? __('Disabling Push Notifications...')
							: __('Enabling Push Notifications...')
					}}
				</span>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronLeft } from 'lucide-vue-next'
import { Button, LoadingIndicator, Switch } from 'frappe-ui'

import { raiseToast } from '@/utils'

const emit = defineEmits(['close'])

const isPushNotificationsEnabled = ref(window.frappePushNotification?.isNotificationEnabled())
const isLoading = ref(false)

const hasPushRelayServer = computed(() => window.frappe?.boot.push_relay_server_url)

const description = computed(() =>
	!hasPushRelayServer.value ? __('Push notifications have been disabled on your site') : '',
)

const togglePushNotifications = async (isEnabled: boolean) => {
	if (isEnabled) return enablePushNotifications()

	isLoading.value = true
	try {
		await window.frappePushNotification.disableNotification()
		isPushNotificationsEnabled.value = false
		raiseToast(__('Push notifications disabled'))
	} catch (error) {
		raiseToast(__(error.message), 'error')
	}
	isLoading.value = false
}

const enablePushNotifications = async () => {
	isLoading.value = true
	try {
		const data = await window.frappePushNotification.enableNotification()
		if (data.permission_granted) isPushNotificationsEnabled.value = true
		else {
			raiseToast(__('Push Notification permission denied'), 'error')
			isPushNotificationsEnabled.value = false
		}
	} catch (error) {
		raiseToast(__(error.message), 'error')
		isPushNotificationsEnabled.value = false
	}
	isLoading.value = false
}
</script>
