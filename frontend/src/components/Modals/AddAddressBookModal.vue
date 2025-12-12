<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('New Address Book'),
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled: !addressBook.name,
					onClick: createAddressBook.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="addressBook.name"
					:label="__('Name')"
					:placeholder="__('Work Contacts')"
				/>
				<FormControl
					v-model="addressBook.description"
					type="textarea"
					:label="__('Description')"
					:placeholder="__('All my work-related contacts')"
				/>
				<FormControl
					v-model="addressBook.default"
					type="checkbox"
					:label="__('Set as Default')"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { inject, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'

const show = defineModel<boolean>()

const user = inject('$user')
const router = useRouter()

const defaultAddressBook = {
	user: user.data.name,
	name: '',
	description: '',
	default: false,
}

const addressBook = reactive({ ...defaultAddressBook })

const createAddressBook = createResource({
	url: 'mail.client.doctype.address_book.address_book.add_address_book',
	makeParams: () => addressBook,
	onSuccess: (data: string) => {
		raiseToast(__('Address book created.'))
		show.value = false
		router.push({
			name: 'AddressBook',
			params: { addressBookName: data },
		})
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

watch(show, (val) => {
	if (val) Object.assign(addressBook, defaultAddressBook)
})
</script>
