<template>
	<DashboardLayout
		v-if="addressBook?.doc"
		:breadcrumbs="breadcrumbs"
		:badge-label="addressBook.doc?.default ? __('Default') : ''"
		badge-theme="blue"
	>
		<template #actions>
			<Dropdown :options="dropdownOptions">
				<Button icon="more-horizontal" class="text-ink-gray-5" />
			</Dropdown>
		</template>
		<template #default>
			<DashboardCard
				:title="__('General Information')"
				:button-label="__('Edit')"
				@action="showEditGeneral = true"
			>
				<InformationField :label="__('Name')" :value="addressBook.doc._name" />
				<InformationField
					:label="__('Description')"
					:value="addressBook.doc.description"
				/>
				<InformationField
					:label="__('Total Contacts')"
					:value="contacts.data?.length.toString() || '0'"
				/>
			</DashboardCard>

			<DashboardCard :title="__('Contacts')" class="flex-1" @action="showAddContacts = true">
				<div class="space-y-4 p-4">
					<FormControl v-model="search" :placeholder="__('Search')" class="w-80">
						<template #prefix>
							<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
						</template>
					</FormControl>

					<ListView
						v-if="contacts?.data"
						ref="listView"
						:columns="LIST_COLUMNS"
						:rows="contacts?.data"
						:options="LIST_OPTIONS"
						row-key="id"
						class="max-h-[50rem] min-h-72 flex-1 overflow-auto"
					>
						<ListHeader />
						<ListRows v-if="contacts.data.length" @scroll="loadMoreContacts" />
						<ListEmptyState v-else />
						<ListSelectBanner>
							<template #actions>
								<Button
									variant="ghost"
									theme="red"
									:label="__('Remove')"
									@click="showRemoveContacts = true"
								/>
							</template>
						</ListSelectBanner>
					</ListView>
				</div>
			</DashboardCard>
		</template>
	</DashboardLayout>

	<EditAddressBookModal
		v-if="addressBook?.originalDoc"
		v-model="showEditGeneral"
		:name="addressBook.doc._name"
		:description="addressBook.doc.description"
		:is-default="!!addressBook.doc.default"
		@save="
			(val) => {
				addressBook.doc._name = val.name
				addressBook.doc.description = val.description
				addressBook.doc.default = Number(val.isDefault)
				addressBook.save.submit()
			}
		"
	/>
	<Dialog v-model="showDeleteAddressBook" :options="deleteAddressBookOptions" />

	<AddAddressBookContactsModal
		v-if="addressBook?.originalDoc"
		v-model="showAddContacts"
		@add="(val) => addContacts.submit(val.map((c) => c.id))"
	/>
	<Dialog v-model="showRemoveContacts" :options="removeContactsOptions" />
</template>

<script setup lang="ts">
import { computed, inject, ref, useTemplateRef } from 'vue'
import { useRouter } from 'vue-router'
import { useDebounceFn, watchDebounced } from '@vueuse/core'
import { Pin, Trash2 } from 'lucide-vue-next'
import {
	Button,
	Dialog,
	Dropdown,
	FeatherIcon,
	FormControl,
	ListEmptyState,
	ListHeader,
	ListRows,
	ListSelectBanner,
	ListView,
	createDocumentResource,
	createResource,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'
import DashboardCard from '@/components/DashboardCard.vue'
import DashboardLayout from '@/components/DashboardLayout.vue'
import InformationField from '@/components/InformationField.vue'
import AddAddressBookContactsModal from '@/components/Modals/AddAddressBookContactsModal.vue'
import EditAddressBookModal from '@/components/Modals/EditAddressBookModal.vue'

const { addressBookName } = defineProps<{ addressBookName: string }>()

const user = inject('$user')
const router = useRouter()
const { addressBooks } = userStore()

const showEditGeneral = ref(false)
const showDeleteAddressBook = ref(false)
const showAddContacts = ref(false)
const showRemoveContacts = ref(false)

const addressBook = createDocumentResource({
	doctype: 'Address Book',
	name: `${user.data.name}|${addressBookName}`,
	onError: () => router.replace({ name: 'AddressBooks' }),
	setValue: {
		onSuccess: () => {
			raiseToast(__('Address book updated.'))
			addressBooks.reload()
		},
		onError: (error) => {
			raiseToast(error.messages[0], 'error')
			addressBook.reload()
		},
	},
})

const search = ref('')
const limit = ref(50)

const contacts = createResource({
	url: 'mail.api.contacts.get_contact_cards',
	auto: true,
	makeParams: () => ({
		filter: { inAddressBook: addressBookName, text: search.value },
		limit: limit.value,
	}),
	transform: (data) =>
		data.map((c) => {
			let email = ''
			if (c.emails.length === 1) email = c.emails[0].address
			else if (c.emails.length > 1)
				email = __('{0} + {1} more', [c.emails[0].address, c.emails.length - 1])

			return { ...c, email }
		}),
	cache: ['contacts', addressBookName, search.value, limit.value],
})

watchDebounced(() => search.value, contacts.reload, { debounce: 300 })

const loadMoreContacts = useDebounceFn((e) => {
	const { scrollTop, scrollHeight, clientHeight } = e.target
	if (scrollTop + clientHeight >= scrollHeight - 10 && contacts.data?.length === limit.value) {
		limit.value += 50
		contacts.reload()
		setTimeout(
			() => e.target.scrollTo({ top: e.target.scrollHeight, behavior: 'smooth' }),
			100,
		)
	}
}, 500)

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

const listView = useTemplateRef('listView')

const addContacts = createResource({
	url: 'mail.client.doctype.contact_card.contact_card.contact_card_add_to_address_book',
	makeParams: (ids) => ({ user: user.data.name, ids, address_book_id: addressBookName }),
	onSuccess: () => {
		raiseToast(__('Contacts added.'))
		contacts.reload()
	},
	onError: (error) => raiseToast(error.messages[0], 'error'),
})

const removeContacts = createResource({
	url: 'mail.client.doctype.contact_card.contact_card.contact_card_remove_from_address_book',
	makeParams: () => ({
		user: user.data.name,
		ids: Array.from(listView.value?.selections),
		address_book_id: addressBookName,
	}),
	onSuccess: () => {
		contacts.reload()
		showRemoveContacts.value = false
		raiseToast(__('Contacts removed.'))
		listView.value?.toggleAllRows()
	},
	onError: (error) => {
		showRemoveContacts.value = false
		raiseToast(error.messages[0], 'error')
	},
})

const deleteAddressBookOptions = computed(() => ({
	title: __('Delete Address Book'),
	message: __('Are you sure you want to delete {0}?', [addressBook.doc?._name]),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: deleteAddressBook.submit }],
}))

const removeContactsOptions = computed(() => ({
	title: __('Remove Contacts'),
	message: __('Are you sure you want to remove the selected contacts?'),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: removeContacts.submit }],
}))

const dropdownOptions = computed(() => [
	{
		label: __('Set as Default'),
		icon: Pin,
		onClick: () => {
			addressBook.doc.default = 1
			addressBook.save.submit()
		},
		condition: () => !addressBook.doc?.default,
	},
	{
		label: __('Delete'),
		icon: Trash2,
		onClick: () => (showDeleteAddressBook.value = true),
	},
])

const LIST_COLUMNS = [
	{ label: __('Name'), key: 'full_name' },
	{ label: __('Kind'), key: 'kind' },
	{ label: __('Email'), key: 'email' },
]

const LIST_OPTIONS = {
	showTooltip: false,
	emptyState: { description: __('No contacts found.') },
	getRowRoute: (row) => ({ name: 'Contact', params: { contactName: row.id } }),
}
</script>
