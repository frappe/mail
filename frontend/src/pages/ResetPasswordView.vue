<template>
	<form class="flex flex-col space-y-4" @submit.prevent="resetPassword.submit()">
		<FormControl
			:label="__('Email')"
			:value="user.data"
			autocomplete="email"
			readonly
			required
		/>
		<FormControl
			v-model="password"
			:label="__('New Password')"
			type="password"
			placeholder="••••••••"
			name="password"
			autocomplete="new-password"
			required
		/>
		<ErrorMessage :message="resetPassword.error" />
		<Button
			variant="solid"
			:loading="resetPassword.loading"
			:label="__('Confirm')"
			type="submit"
		/>
	</form>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button, ErrorMessage, FormControl, createResource } from 'frappe-ui'

const { requestKey } = defineProps<{ requestKey: string }>()

const router = useRouter()

const password = ref('')

const user = createResource({
	url: 'mail.api.account.get_user_for_reset_password_key',
	auto: true,
	makeParams: () => ({ key: requestKey }),
	onSuccess: (data?: string) => {
		if (!data) router.replace('/reset-password')
	},
	onError: () => router.replace('/reset-password'),
})

const resetPassword = createResource({
	url: 'frappe.core.doctype.user.user.update_password',
	makeParams: () => ({ key: requestKey, new_password: password.value }),
	onSuccess: () => window.location.reload(),
})
</script>
