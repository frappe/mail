<template>
	<DashboardLayout
		:breadcrumbs="[{ label: __('Contacts') }]"
		:button-label="__('Add Contact')"
		:button-action="() => (showAddContact = true)"
	>
		<div class="flex items-center space-x-3">
			<FormControl v-model="search" :placeholder="__('Search')" class="w-80">
				<template #prefix>
					<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
				</template>
			</FormControl>
		</div>
		<ListView
			v-if="contacts?.data"
			ref="listView"
			class="flex-1"
			:columns="LIST_COLUMNS"
			:rows="contacts.data"
			:options="LIST_OPTIONS"
			row-key="name"
		>
			<ListHeader />
			<ListRows v-if="searchedContacts.length" />
			<ListEmptyState v-else />
			<ListSelectBanner>
				<template #actions>
					<Button
						variant="ghost"
						theme="red"
						:label="__('Delete')"
						@click="showDeleteContacts = true"
					/>
				</template>
			</ListSelectBanner>
		</ListView>
	</DashboardLayout>

	<Dialog v-model="showDeleteContacts" :options="DELETE_CONTACTS_OPTIONS" />
</template>

<script setup lang="ts">
import { computed, inject, ref, useTemplateRef } from 'vue'
import {
	Button,
	Dialog,
	FeatherIcon,
	FormControl,
	ListEmptyState,
	ListHeader,
	ListRows,
	ListSelectBanner,
	ListView,
	createResource,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import DashboardLayout from '@/components/DashboardLayout.vue'

const user = inject('$user')

const listView = useTemplateRef('listView')

const showAddContact = ref(false)
const showDeleteContacts = ref(false)
const search = ref('')

const contacts = createResource({
	url: 'mail.api.contacts.get_contact_cards',
	auto: true,
	cache: ['contacts', user.data.name],
})

const deleteContacts = createResource({
	url: 'mail.client.doctype.contact_card.contact_card.bulk_delete',
	makeParams: () => ({ names: Array.from(listView.value?.selections) }),
	onSuccess: () => {
		contacts.reload()
		showDeleteContacts.value = false
		raiseToast(__('Contacts deleted.'))
		listView.value?.toggleAllRows()
	},
	onError: (error) => {
		showDeleteContacts.value = false
		raiseToast(error.messages[0], 'error')
	},
})

const searchedContacts = computed(() =>
	contacts.data?.filter((c) => c.full_name.toLowerCase().includes(search.value.toLowerCase())),
)

const LIST_COLUMNS = [
	{ label: __('Name'), key: 'full_name' },
	{ label: __('Kind'), key: 'kind' },
]

const LIST_OPTIONS = {
	showTooltip: false,
	emptyState: { description: __('No contacts found.') },
	// getRowRoute: (row) => ({ name: 'AddressBook', params: { addressBookName: row.id } }),
}

const DELETE_CONTACTS_OPTIONS = {
	title: __('Delete Contacts'),
	message: __('Are you sure you want to delete the selected contacts?'),
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: deleteContacts.submit }],
}
</script>
