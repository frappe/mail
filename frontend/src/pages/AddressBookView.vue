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
				<InformationField :label="__('Total Contacts')" :value="'1'" />
			</DashboardCard>

			<DashboardCard :title="__('Contacts')" class="flex-1" @action="showEditGeneral = true">
				<div class="space-y-4 p-4">
					<FormControl v-model="search" :placeholder="__('Search')" class="w-80">
						<template #prefix>
							<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
						</template>
					</FormControl>

					<ListView
						ref="listView"
						:columns="LIST_COLUMNS"
						:rows="[]"
						:options="LIST_OPTIONS"
						row-key="id"
					>
						<ListHeader />
						<ListRows v-if="false" />
						<ListEmptyState v-else />
						<ListSelectBanner>
							<template #actions>
								<Button variant="ghost" theme="red" :label="__('Delete')" />
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
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useRouter } from 'vue-router'
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
import EditAddressBookModal from '@/components/Modals/EditAddressBookModal.vue'

const { addressBookName } = defineProps<{ addressBookName: string }>()

const user = inject('$user')
const router = useRouter()
const { addressBooks } = userStore()

const showEditGeneral = ref(false)
const showDeleteAddressBook = ref(false)
const search = ref('')

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

const dropdownOptions = computed(() => [
	{
		label: __('Set as Default'),
		onClick: () => {
			addressBook.doc.default = 1
			addressBook.save.submit()
		},
		icon: Pin,
		condition: () => !addressBook.doc?.default,
	},
	{
		label: __('Delete'),
		onClick: () => (showDeleteAddressBook.value = true),
		icon: Trash2,
	},
])

const LIST_COLUMNS = [
	{ label: __('Name'), key: 'full_name' },
	{ label: __('Kind'), key: 'kind' },
]

const LIST_OPTIONS = {
	showTooltip: false,
	emptyState: { description: __('No contacts found.') },
	getRowRoute: (row) => ({ name: 'Contact', params: { contactName: row.id } }),
}
</script>
