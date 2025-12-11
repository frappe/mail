<template>
	<DashboardLayout
		:breadcrumbs="[{ label: __('Mailing Lists') }]"
		:button-label="__('Add Mailing List')"
		:button-action="() => (showAddList = true)"
	>
		<div class="flex items-center space-x-3">
			<FormControl v-model="search" :placeholder="__('Search')" class="w-80">
				<template #prefix>
					<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
				</template>
			</FormControl>
		</div>
		<ListView
			v-if="lists?.data"
			ref="listView"
			class="flex-1"
			:columns="LIST_COLUMNS"
			:rows="lists.data"
			:options="LIST_OPTIONS"
			row-key="name"
		>
			<ListHeader />
			<ListRows v-if="lists.data.length" />
			<ListEmptyState v-else />
			<ListSelectBanner>
				<template #actions>
					<Button
						variant="ghost"
						theme="red"
						:label="__('Delete')"
						@click="showDeleteLists = true"
					/>
				</template>
			</ListSelectBanner>
		</ListView>
	</DashboardLayout>
	<AddMailingListModal v-model="showAddList" />
	<Dialog v-model="showDeleteLists" :options="deleteListsOptions" />
</template>

<script setup lang="ts">
import { inject, ref, useTemplateRef } from 'vue'
import { watchDebounced } from '@vueuse/core'
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
import AddMailingListModal from '@/components/Modals/AddMailingListModal.vue'

const user = inject('$user')

const listView = useTemplateRef('listView')

const search = ref('')

const showAddList = ref(false)
const showDeleteLists = ref(false)

const lists = createResource({
	url: 'mail.api.admin.get_mailing_lists',
	auto: true,
	makeParams: () => ({ txt: search.value }),
	transform: (data) => data.map((l) => ({ ...l, total_members: l.total_members.toString() })),
	cache: ['mailTenantMailingLists', user.data?.tenant, search.value],
})

watchDebounced(() => search.value, lists.reload, { debounce: 500 })

const deleteLists = createResource({
	url: 'mail.api.admin.delete_mailing_lists',
	makeParams: () => ({ names: Array.from(listView.value?.selections) }),
	onSuccess: () => {
		lists.reload()
		showDeleteLists.value = false
		raiseToast(__('Mailing lists deleted.'))
		listView.value?.toggleAllRows()
	},
	onError: (error) => {
		showDeleteLists.value = false
		raiseToast(error.messages[0], 'error')
	},
})

const deleteListsOptions = {
	title: __('Delete Mailing Lists'),
	message: __('Are you sure you want to delete the selected mailing lists?'),
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: deleteLists.submit }],
}

const LIST_OPTIONS = {
	showTooltip: false,
	emptyState: { description: __('No mailing lists found.') },
	getRowRoute: (row) => ({ name: 'MailingList', params: { listName: row.name } }),
}

const LIST_COLUMNS = [
	{ label: __('Mailing List'), key: 'name' },
	{ label: __('Total Members'), key: 'total_members' },
]
</script>
