<template>
	<h1>{{ __('Profile') }}</h1>

	<div class="flex w-full items-center">
		<Avatar
			:image="user.data?.user_image"
			:label="user.data?.full_name"
			size="3xl"
			class="h-16 w-16"
		/>
		<div class="mx-4 flex flex-col">
			<span class="text-xl font-semibold">{{ user.data?.full_name }}</span>
			<span class="text-ink-gray-6 text-base">{{ user.data?.email }}</span>
		</div>
		<Button :label="__('Edit Photo')" class="ml-auto" @click="showEditPhoto = true" />
	</div>
	<FormControl v-model="firstName" :label="__('First Name')" variant="outline" />
	<FormControl v-model="lastName" :label="__('Last Name')" variant="outline" />
	<ErrorMessage :message="setName.error" />
	<Button
		:label="__('Save')"
		class="min-h-7"
		variant="solid"
		:disabled="
			!firstName ||
			(firstName === user.data?.first_name && lastName === user.data?.last_name)
		"
		:loading="setName.isLoading"
		@click="setName.submit"
	/>
	<Button class="min-h-7" :label="__('Change Password')" @click="showChangePassword = true" />

	<EditPhotoModal v-model="showEditPhoto" />
	<ChangePasswordModal v-model="showChangePassword" />
</template>
<script setup lang="ts">
import { inject, ref } from 'vue'
import { Avatar, Button, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import ChangePasswordModal from '@/components/Modals/ChangePasswordModal.vue'
import EditPhotoModal from '@/components/Modals/EditPhotoModal.vue'

const user = inject('$user')

const showEditPhoto = ref(false)
const showChangePassword = ref(false)

const firstName = ref(user.data?.first_name)
const lastName = ref(user.data?.last_name)

const setName = createResource({
	url: 'frappe.client.set_value',
	makeParams: () => ({
		doctype: 'User',
		name: user.data?.name,
		fieldname: { first_name: firstName.value, last_name: lastName.value },
	}),
	onSuccess: () => {
		raiseToast(__('Profile updated.'))
		user.reload()
	},
})
</script>
