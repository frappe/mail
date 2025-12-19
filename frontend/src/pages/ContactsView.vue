<template>
	<DashboardLayout
		:breadcrumbs="[{ label: __('Contacts') }]"
		:button-label="__('Add Contact')"
		:button-action="() => (showAddContact = true)"
	>
		<FormControl v-model="search" :placeholder="__('Search')" class="w-80">
			<template #prefix>
				<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
			</template>
		</FormControl>

		<ListView
			v-if="contacts?.data"
			ref="listView"
			class="flex-1"
			:columns="LIST_COLUMNS"
			:rows="contacts.data"
			:options="LIST_OPTIONS"
			row-key="id"
		>
			<ListHeader />
			<ListRows v-if="contacts.data.length" @scroll="loadMoreContacts" />
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

	<AddContactModal v-model="showAddContact" />
	<Dialog v-model="showDeleteContacts" :options="DELETE_CONTACTS_OPTIONS" />
</template>

<script setup lang="ts">
import { inject, ref, useTemplateRef } from 'vue'
import { useDebounceFn, watchDebounced } from '@vueuse/core'
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
import AddContactModal from '@/components/Modals/AddContactModal.vue'

const user = inject('$user')

const listView = useTemplateRef('listView')

const showAddContact = ref(false)
const showDeleteContacts = ref(false)
const search = ref('')
const limit = ref(50)

const contacts = createResource({
	url: 'mail.api.contacts.get_contact_cards',
	auto: true,
	makeParams: () => ({ filter: { text: search.value }, limit: limit.value }),
	cache: ['contacts', user.data.name, search.value, limit.value],
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

const deleteContacts = createResource({
	url: 'mail.client.doctype.contact_card.contact_card.delete_contact_cards',
	makeParams: () => ({ user: user.data.name, ids: Array.from(listView.value?.selections) }),
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

const LIST_COLUMNS = [
	{ label: __('Name'), key: 'full_name' },
	{ label: __('Kind'), key: 'kind' },
]

const LIST_OPTIONS = {
	showTooltip: false,
	emptyState: { description: __('No contacts found.') },
	getRowRoute: (row) => ({ name: 'Contact', params: { contactName: row.id } }),
}

const DELETE_CONTACTS_OPTIONS = {
	title: __('Delete Contacts'),
	message: __('Are you sure you want to delete the selected contacts?'),
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: deleteContacts.submit }],
}
</script>
