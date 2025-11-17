<template>
	<form class="flex flex-col space-y-4" @submit.prevent="submit">
		<FormControl
			v-model="email"
			:label="__('Email')"
			type="email"
			placeholder="johndoe@example.com"
			autocomplete="email"
			:readonly="!!requestKey || isVerificationStep"
			required
		/>
		<FormControl
			v-if="isVerificationStep"
			v-model="otp"
			:label="__('Verification Code')"
			placeholder="5 digit verification code"
			maxlength="5"
			autocomplete="one-time-code"
			required
		/>
		<template v-if="requestKey">
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
		</template>
		<ErrorMessage :message="errorMessage" />
		<Button
			variant="solid"
			:loading="signUp.loading || verifyOtp.loading || createAccount.loading"
			:label="buttonLabel"
			type="submit"
		/>
		<Button
			v-if="isVerificationStep"
			:loading="resendOtp.loading"
			:label="__('Resend OTP')"
			@click="resendOtp.submit()"
		/>
	</form>
	<div class="mt-6 text-center">
		<router-link class="text-center text-base font-medium hover:underline" to="/login">
			{{ __('Already have an account? Log in.') }}
		</router-link>
	</div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Button, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { sessionStore } from '@/stores/session'

const { requestKey } = defineProps<{ requestKey?: string }>()

const router = useRouter()
const { login } = sessionStore()

const isVerificationStep = ref(false)
const email = ref('')
const otp = ref('')
const firstName = ref('')
const lastName = ref('')
const password = ref('')
const accountRequest = ref('')
const errorMessage = ref('')

const buttonLabel = computed(() => {
	if (requestKey) return 'Create Account'
	return __(isVerificationStep.value ? 'Verify' : 'Sign Up')
})

createResource({
	url: 'mail.api.get_signup_settings',
	auto: true,
	onSuccess: (data) => {
		if (!(Number(data.allow_business_signup) || requestKey)) router.push('/signup')
	},
})

const signUp = createResource({
	url: 'mail.api.account.business_signup',
	makeParams: () => ({ email: email.value }),
	onSuccess: (data) => {
		errorMessage.value = ''
		accountRequest.value = data
		isVerificationStep.value = true
		raiseToast('A verification code has been sent to your registered email address.')
	},
	onError: (error) => (errorMessage.value = error.messages[0]),
})

const resendOtp = createResource({
	url: 'mail.api.account.resend_otp',
	makeParams: () => ({ account_request: accountRequest.value }),
	onSuccess: () =>
		raiseToast('A verification code has been sent to your registered email address.'),
	onError: (error) => raiseToast(error.messages[0], 'error'),
})

const verifyOtp = createResource({
	url: 'mail.api.account.verify_otp',
	makeParams: () => ({ account_request: accountRequest.value, otp: otp.value }),
	onSuccess: (requestKey) => {
		errorMessage.value = ''
		router.push({ name: 'BusinessSetup', params: { requestKey } })
	},
	onError: (error) => (errorMessage.value = error.messages[0]),
})

const getAccountRequest = createResource({
	url: 'mail.api.account.get_account_request',
	makeParams: () => ({ request_key: requestKey }),
	onSuccess: (data) => {
		if ((data?.email || data?.account) && !data?.is_verified && !data?.is_expired)
			email.value = data.account || data.email
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
		isVerificationStep.value = false
		if (!val) return
		if (val.length === 32) getAccountRequest.submit()
		else router.replace({ name: 'SignUp' })
	},
	{ immediate: true },
)

const submit = () => {
	if (requestKey) createAccount.submit()
	else if (isVerificationStep.value) verifyOtp.submit()
	else signUp.submit()
}
</script>
