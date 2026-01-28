<template>
	<div class="sm:bg-surface-gray-1 min-h-screen">
		<div class="relative z-[1] mx-auto py-8 sm:w-max sm:py-32">
			<div class="flex">
				<slot name="logo">
					<div class="mx-auto flex items-center space-x-2">
						<MailLogo class="inline-block h-7 w-7" />
						<span class="select-none text-xl font-semibold tracking-tight">
							Frappe Mail
						</span>
					</div>
				</slot>
			</div>
			<div
				class="bg-surface-white mx-auto w-full px-4 py-8 sm:mt-6 sm:w-[26rem] sm:rounded-lg sm:px-8 sm:shadow-xl"
			>
				<div class="mb-6 text-center">
					<span class="text-center text-lg font-medium leading-5 tracking-tight">
						{{ title }}
					</span>
				</div>
				<slot />
			</div>
		</div>
		<div class="absolute bottom-4 flex w-full justify-center">
			<FrappeLogo class="h-4" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import FrappeLogo from '@/components/Icons/FrappeLogo.vue'
import MailLogo from '@/components/Icons/MailLogo.vue'

const route = useRoute()

const title = computed(() => {
	switch (route.name) {
		case 'Login':
			return __('Sign in to your account')
		case 'Setup':
			return __('Set up organization')
		case 'ForgotPassword':
		case 'ResetPassword':
			return __('Reset Password')
		default:
			return __('Create a new account')
	}
})
</script>
