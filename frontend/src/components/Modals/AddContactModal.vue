<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('New Contact'),
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled: !(
						contact.full_name &&
						contact.kind &&
						contact.address_book_ids.length
					),
					onClick: createContact.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="contact.full_name"
					:label="__('Name')"
					:placeholder="__('John Doe')"
				/>
				<FormControl
					v-model="contact.kind"
					type="select"
					:label="__('Kind')"
					:options="KIND_OPTIONS"
				/>
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Address Books') }}</label>
					<MultiSelect
						v-model="contact.address_book_ids"
						:options="
							addressBooks.data.map((ab) => ({ label: ab._name, value: ab.id }))
						"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { inject, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, FormControl, MultiSelect, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

const show = defineModel<boolean>()

const user = inject('$user')
const { addressBooks } = userStore()
const router = useRouter()

const defaultAddressBook = addressBooks.data.find((ab) => ab.default)?.id

const defaultContact = {
	user: user.data.name,
	address_book_ids: defaultAddressBook ? [defaultAddressBook] : [],
	full_name: '',
	kind: 'Personal',
}

const contact = reactive({ ...defaultContact })

const createContact = createResource({
	url: 'mail.client.doctype.contact_card.contact_card.add_contact_card',
	makeParams: () => contact,
	onSuccess: (data: string) => {
		raiseToast(__('Contact created.'))
		show.value = false
		router.push({ name: 'Contact', params: { contactName: data } })
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

watch(show, (val) => {
	if (val) Object.assign(contact, defaultContact)
})

const KIND_OPTIONS = [
	{ label: __('Individual'), value: 'Individual' },
	{ label: __('Group'), value: 'Group' },
	{ label: __('Other'), value: 'Other' },
]
</script>
