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
					<MultiSelect v-model="contact.address_book_ids" :options="addressBooks.data" />
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

const show = defineModel<boolean>()

const user = inject('$user')
const router = useRouter()

const defaultContact = {
	user: user.data.name,
	address_book_ids: [],
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

const addressBooks = createResource({
	url: 'mail.api.contacts.get_address_books',
	auto: true,
	makeParams: () => ({ user: user.data.name }),
	transform: (data) => data.map((ab) => ({ label: ab._name, value: ab.id })),
	cache: ['addressBooks', user.data.name],
})

watch(show, (val) => {
	if (val) Object.assign(contact, defaultContact)
})

const KIND_OPTIONS = [
	{ label: __('Personal'), value: 'Personal' },
	{ label: __('Work'), value: 'Work' },
	{ label: __('Other'), value: 'Other' },
]
</script>
