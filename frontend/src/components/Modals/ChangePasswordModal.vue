<template>
	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="currentPassword"
					type="password"
					:label="__('Current Password')"
					placeholder="••••••••"
					variant="outline"
				/>
				<FormControl
					v-model="newPassword"
					type="password"
					:label="__('New Password')"
					placeholder="••••••••"
					variant="outline"
				/>
				<FormControl
					v-model="confirmPassword"
					type="password"
					:label="__('Confirm New Password')"
					placeholder="••••••••"
					variant="outline"
				/>
				<ErrorMessage :message="errorMessage" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Dialog, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'

const show = defineModel<boolean>()

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')

const errorMessage = computed(() =>
	confirmPassword.value && confirmPassword.value !== newPassword.value
		? __('Passwords do not match')
		: updatePassword.error,
)

const dialogOptions = computed(() => ({
	title: __('Change Password'),
	actions: [
		{
			label: __('Confirm'),
			variant: 'solid',
			onClick: () => updatePassword.submit(),
			disabled:
				!(currentPassword.value.length && newPassword.value.length) ||
				confirmPassword.value !== newPassword.value,
		},
	],
}))

const updatePassword = createResource({
	url: 'frappe.core.doctype.user.user.update_password',
	makeParams: () => ({ old_password: currentPassword.value, new_password: newPassword.value }),
	onSuccess: () => {
		show.value = false
		raiseToast(__('Password updated successfully'))
	},
})

watch(show, () => {
	currentPassword.value = ''
	newPassword.value = ''
	confirmPassword.value = ''
})
</script>
