<template>
	<DashboardLayout
		v-if="addressBook?.doc"
		:breadcrumbs="breadcrumbs"
		:badge-label="addressBook.doc?.default ? __('Default') : ''"
		badge-theme="blue"
	>
		<template #actions>
			<Dropdown :options="DROPDOWN_OPTIONS">
				<Button icon="more-horizontal" class="text-ink-gray-5" />
			</Dropdown>
		</template>
		<template #default>
			<div class="grid sm:grid-cols-2">
				<DashboardCard
					:title="__('General Information')"
					:button-label="__('Edit')"
					class="col-span-2"
					@action="showEditGeneral = true"
				>
					<InformationField :label="__('Name')" :value="addressBook.doc._name" />
					<InformationField
						:label="__('Description')"
						:value="addressBook.doc.description"
					/>
					<InformationField :label="__('Total Contacts')" :value="'1'" />
				</DashboardCard>
			</div>
		</template>
	</DashboardLayout>

	<EditAddressBookModal
		v-if="addressBook?.originalDoc"
		v-model="showEditGeneral"
		:name="addressBook.doc._name"
		:description="addressBook.doc.description"
		@save="
			(val) => {
				addressBook.doc._name = val.name
				addressBook.doc.description = val.description
				addressBook.save.submit()
			}
		"
	/>
	<Dialog v-model="showDeleteAddressBook" :options="deleteAddressBookOptions" />
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Trash2 } from 'lucide-vue-next'
import { Button, Dialog, Dropdown, createDocumentResource, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'
import DashboardCard from '@/components/DashboardCard.vue'
import DashboardLayout from '@/components/DashboardLayout.vue'
import InformationField from '@/components/InformationField.vue'
import EditAddressBookModal from '@/components/Modals/EditAddressBookModal.vue'

const { addressBookName } = defineProps<{ addressBookName: string }>()

const user = inject('$user')
const router = useRouter()
const { addressBooks } = userStore()

const showEditGeneral = ref(false)
const showDeleteAddressBook = ref(false)

const addressBook = createDocumentResource({
	doctype: 'Address Book',
	name: `${user.data.name}|${addressBookName}`,
	onError: () => router.replace({ name: 'AddressBooks' }),
	setValue: {
		onSuccess: () => {
			raiseToast(__('Address book updated.'))
		},
		onError: (error) => {
			raiseToast(error.messages[0], 'error')
			addressBook.reload()
		},
	},
})

const breadcrumbs = computed(() => [
	{ label: __('Address Books'), route: '/address-books' },
	{ label: addressBook.doc?._name || addressBookName },
])

const deleteAddressBook = createResource({
	url: 'mail.client.doctype.address_book.address_book.delete_address_book',
	makeParams: () => ({ user: user.data.name, id: addressBookName }),
	onSuccess: () => {
		showDeleteAddressBook.value = false
		raiseToast(__('Address book deleted.'))
		addressBooks.reload()
		router.push({ name: 'AddressBooks' })
	},
	onError: (error) => {
		showDeleteAddressBook.value = false
		raiseToast(error.messages[0], 'error')
	},
})

const deleteAddressBookOptions = computed(() => ({
	title: __('Delete Address Book'),
	message: __('Are you sure you want to delete {0}?', [addressBook.doc?._name]),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: deleteAddressBook.submit }],
}))

const DROPDOWN_OPTIONS = [
	{
		label: __('Delete'),
		onClick: () => (showDeleteAddressBook.value = true),
		icon: Trash2,
	},
]
</script>
