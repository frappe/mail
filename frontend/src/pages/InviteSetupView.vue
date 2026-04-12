<template>
	<form class="flex flex-col space-y-4" @submit.prevent="submit">
		<FormControl
			v-model="email"
			:label="__('Email')"
			type="email"
			placeholder="johndoe@example.com"
			autocomplete="email"
			readonly
			required
		/>
		<FormControl
			v-model="firstName"
			:label="__('First Name')"
			placeholder="John"
			autocomplete="given-name"
			required
		/>
		<FormControl
			v-model="lastName"
			:label="__('Last Name')"
			placeholder="Doe"
			autocomplete="family-name"
		/>
		<FormControl
			v-model="password"
			:label="__('Password')"
			type="password"
			placeholder="••••••••"
			name="password"
			autocomplete="current-password"
			required
		/>
		<ErrorMessage :message="errorMessage" />
		<Button
			variant="solid"
			:loading="createAccount.loading"
			:label="__('Create Account')"
			type="submit"
		/>
	</form>
	<div class="mt-6 text-center">
		<router-link class="text-center text-base font-medium hover:underline" to="/login">
			{{ __('Already have an account? Log in.') }}
		</router-link>
	</div>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { sessionStore } from '@/stores/session'

const { requestKey } = defineProps<{ requestKey: string }>()

const router = useRouter()
const { login } = sessionStore()

const email = ref('')
const firstName = ref('')
const lastName = ref('')
const password = ref('')
const errorMessage = ref('')

const getAccountRequest = createResource({
	url: 'mail.api.account.get_account_request',
	makeParams: () => ({ request_key: requestKey }),
	onSuccess: (data) => {
		if ((data?.backup_email || data?.account) && !data?.is_verified && !data?.is_expired)
			email.value = data.account || data.backup_email
		else router.replace({ name: 'SignUp' })
	},
})

const createAccount = createResource({
	url: 'mail.api.account.create_account',
	makeParams: () => ({
		request_key: requestKey,
		first_name: firstName.value,
		last_name: lastName.value,
		password: password.value,
	}),
	onSuccess: () => {
		errorMessage.value = ''
		login.submit({ usr: email.value, pwd: password.value })
	},
	onError: (error) => (errorMessage.value = error.messages[0]),
})

watch(
	() => requestKey,
	(val) => {
		if (!val) return
		if (val.length === 32) getAccountRequest.submit()
		else router.replace({ name: 'SignUp' })
	},
	{ immediate: true },
)

const submit = () => createAccount.submit()
</script>
