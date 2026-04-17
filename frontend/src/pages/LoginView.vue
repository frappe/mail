<template>
	<form class="flex flex-col space-y-4" @submit.prevent="login.submit({ usr, pwd })">
		<FormControl
			v-model="usr"
			:label="__('Email')"
			placeholder="johndoe@example.com"
			autocomplete="email"
			required
		/>
		<FormControl
			v-model="pwd"
			:label="__('Password')"
			type="password"
			placeholder="••••••••"
			name="password"
			autocomplete="current-password"
			required
		/>
		<div clas="!mt-2">
			<router-link class="text-sm hover:underline" to="/reset-password">
				{{ __('Forgot password?') }}
			</router-link>
		</div>
		<ErrorMessage :message="login.error" />
		<Button variant="solid" :loading="login.loading" :label="__('Log In')" type="submit" />
	</form>
	<div v-if="Number(signupSettings.data?.allow_signup)" class="mt-6 text-center">
		<router-link class="text-center text-base font-medium hover:underline" to="/signup">
			{{ __('New member? Create an account.') }}
		</router-link>
	</div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { Button, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { sessionStore } from '@/stores/session'

const { login } = sessionStore()

const usr = ref('')
const pwd = ref('')

const signupSettings = createResource({ url: 'mail.api.get_signup_settings', auto: true })
</script>
