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
			<FormControl
				v-model="status"
				:placeholder="__('Status')"
				class="w-40"
				type="select"
				:options="STATUS_OPTIONS"
			/>
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
			<ListRows>
				<template v-if="lists.data.length">
					<ListRow
						v-for="row in lists.data"
						:key="row.name"
						v-slot="{ column, item }"
						:row="row"
						class="hover:!bg-surface-gray-1"
					>
						<ListRowItem :item="item">
							<Badge
								v-if="column.key == 'enabled'"
								:theme="item ? 'green' : 'red'"
								:label="item ? 'Enabled' : 'Disabled'"
							/>
						</ListRowItem>
					</ListRow>
				</template>
				<ListEmptyState v-else />
			</ListRows>
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
import { inject, ref } from 'vue'
import { useDebounce } from '@vueuse/core'
import {
	Badge,
	Button,
	Dialog,
	FeatherIcon,
	FormControl,
	ListEmptyState,
	ListHeader,
	ListRow,
	ListRowItem,
	ListRows,
	ListSelectBanner,
	ListView,
	createResource,
	useList,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import DashboardLayout from '@/components/DashboardLayout.vue'
import AddMailingListModal from '@/components/Modals/AddMailingListModal.vue'

const user = inject('$user')

const listView = ref(null)

const search = ref('')
const debouncedSearch = useDebounce(search, 500)
const status = ref<'Enabled' | 'Disabled' | ''>('')

const showAddList = ref(false)
const showDeleteLists = ref(false)

const lists = useList({
	doctype: 'Mailing List',
	fields: ['name', 'display_name', 'enabled'],
	filters: () => {
		const filters: Record<string, string | string[] | number> = {
			tenant: user.data?.tenant,
			name: ['like', debouncedSearch.value],
		}
		if (status.value) filters.enabled = status.value === 'Enabled' ? 1 : 0
		return filters
	},
	orderBy: 'email asc',
	limit: 100,
	cacheKey: ['mailTenantMailingLists', user.data?.tenant, debouncedSearch.value, status.value],
})

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
	message: __('Are you sure you want to delete the selected lists?'),
	actions: [
		{
			label: __('Confirm'),
			variant: 'solid',
			onClick: deleteLists.submit,
		},
	],
}

const LIST_COLUMNS = [
	{ label: __('Email'), key: 'name' },
	{ label: __('Display Name'), key: 'display_name' },
	{ label: __('Status'), key: 'enabled' },
]

const LIST_OPTIONS = {
	showTooltip: false,
	emptyState: { description: __('No mailing lists found.') },
	getRowRoute: (row) => ({ name: 'MailingList', params: { listName: row.name } }),
}

const STATUS_OPTIONS = [
	{ label: '', value: '' },
	{ label: __('Enabled'), value: 'Enabled' },
	{ label: __('Disabled'), value: 'Disabled' },
]
</script>
