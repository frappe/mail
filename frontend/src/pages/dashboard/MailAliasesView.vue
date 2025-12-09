<template>
	<DashboardLayout
		:breadcrumbs="[{ label: __('Aliases') }]"
		:button-label="__('Add Alias')"
		:button-action="() => (showAddAlias = true)"
	>
		<div class="flex items-center space-x-3">
			<FormControl v-model="search" :placeholder="__('Search')" class="w-80">
				<template #prefix>
					<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
				</template>
			</FormControl>
			<FormControl
				v-model="type"
				:placeholder="__('Type')"
				class="w-40"
				type="select"
				:options="TYPE_OPTIONS"
			/>
			<FormControl
				v-model="status"
				:placeholder="__('Status')"
				class="w-40"
				type="select"
				:options="STATUS_OPTIONS"
			/>
		</div>
		<ListView
			v-if="aliases?.data"
			ref="listView"
			class="flex-1"
			:columns="LIST_COLUMNS"
			:rows="aliases.data"
			:options="LIST_OPTIONS"
			row-key="name"
		>
			<ListHeader />
			<ListRows>
				<template v-if="aliases.data.length">
					<ListRow
						v-for="row in aliases.data"
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
						@click="showDeleteAliases = true"
					/>
				</template>
			</ListSelectBanner>
		</ListView>
	</DashboardLayout>
	<AddAliasModal v-model="showAddAlias" @reload-aliases="aliases.reload()" />
	<EditAliasModal
		v-if="selectedMailAlias"
		v-model="showEditAlias"
		:alias-i-d="selectedMailAlias"
		@reload-aliases="aliases.reload()"
	/>
	<Dialog v-model="showDeleteAliases" :options="deleteAliasesOptions" />
</template>

<script setup lang="ts">
import { inject, ref, useTemplateRef } from 'vue'
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
import AddAliasModal from '@/components/Modals/AddAliasModal.vue'
import EditAliasModal from '@/components/Modals/EditAliasModal.vue'

const user = inject('$user')

const listView = useTemplateRef('listView')

const search = ref('')
const debouncedSearch = useDebounce(search, 500)
const type = ref<'Mail Account' | 'Mailing List' | ''>('')
const status = ref<'Enabled' | 'Disabled' | ''>('')

const selectedMailAlias = ref('')
const showAddAlias = ref(false)
const showEditAlias = ref(false)
const showDeleteAliases = ref(false)

const aliases = useList({
	doctype: 'Mail Alias',
	fields: ['name', 'alias_for_name', 'enabled'],
	filters: () => {
		const filters: Record<string, string | string[] | number> = {
			tenant: user.data?.tenant,
			name: ['like', debouncedSearch.value],
		}
		if (type.value) filters.alias_for_type = type.value
		if (status.value) filters.enabled = status.value === 'Enabled' ? 1 : 0
		return filters
	},
	orderBy: 'email asc',
	limit: 100,
	cacheKey: [
		'mailTenantAliases',
		user.data?.tenant,
		debouncedSearch.value,
		type.value,
		status.value,
	],
})

const deleteAliases = createResource({
	url: 'mail.api.admin.delete_aliases',
	makeParams: () => ({ names: Array.from(listView.value?.selections) }),
	onSuccess: () => {
		aliases.reload()
		showDeleteAliases.value = false
		raiseToast(__('Aliases deleted.'))
		listView.value?.toggleAllRows()
	},
	onError: (error) => {
		showDeleteAliases.value = false
		raiseToast(error.messages[0], 'error')
	},
})

const deleteAliasesOptions = {
	title: __('Delete Aliases'),
	message: __('Are you sure you want to delete the selected aliases?'),
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: deleteAliases.submit }],
}

const LIST_COLUMNS = [
	{ label: __('Alias'), key: 'name' },
	{ label: __('Alias For'), key: 'alias_for_name' },
	{ label: __('Status'), key: 'enabled' },
]

const LIST_OPTIONS = {
	showTooltip: false,
	emptyState: { description: __('No aliases found.') },
	onRowClick: (row) => {
		selectedMailAlias.value = row.name
		showEditAlias.value = true
	},
}

const TYPE_OPTIONS = [
	{ label: '', value: '' },
	{ label: __('User'), value: 'Mail Account' },
	{ label: __('Mailing List'), value: 'Mailing List' },
]

const STATUS_OPTIONS = [
	{ label: '', value: '' },
	{ label: __('Enabled'), value: 'Enabled' },
	{ label: __('Disabled'), value: 'Disabled' },
]
</script>
