<template>
	<div class="flex h-screen flex-col">
		<header class="flex items-center border-b px-5 py-2.5">
			<Breadcrumbs :items="[{ label: __('Mail Exchanges') }]" />
		</header>
		<Tabs
			v-model="tabIndex"
			:tabs="TABS"
			@update:model-value="
				$router.replace({ query: { operation: tabIndex ? 'Export' : 'Import' } })
			"
		>
			<template #tab-panel>
				<div class="m-5 flex flex-1 flex-col space-y-5 overflow-y-auto">
					<div class="flex items-center space-x-3">
						<FormControl
							v-model="status"
							:label="__('Status')"
							type="select"
							:options="STATUS_OPTIONS"
							class="w-40"
						/>
					</div>
					<ListView
						v-if="mailDataExchanges.data"
						:columns="listColumns"
						:rows="mailDataExchanges.data"
						:options="LIST_OPTIONS"
						row-key="name"
						class="flex-1"
					>
						<ListHeader />
						<ListRows>
							<template v-if="mailDataExchanges.data.length">
								<ListRow
									v-for="row in mailDataExchanges.data"
									:key="row.name"
									v-slot="{ item, column }"
									:row="row"
								>
									<ListRowItem :item="item">
										<Badge
											v-if="column.key == 'status'"
											:theme="getTheme(item)"
											:label="item"
										/>
									</ListRowItem>
								</ListRow>
							</template>
							<ListEmptyState v-else />
						</ListRows>
					</ListView>
					<ErrorMessage
						v-if="mailDataExchanges.error"
						:message="mailDataExchanges.error"
					/>
				</div>
			</template>
		</Tabs>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useRoute } from 'vue-router'
import { HardDriveDownload, HardDriveUpload } from 'lucide-vue-next'
import {
	Badge,
	Breadcrumbs,
	ErrorMessage,
	FormControl,
	ListEmptyState,
	ListHeader,
	ListRow,
	ListRowItem,
	ListRows,
	ListView,
	Tabs,
	useList,
} from 'frappe-ui'

import { getTheme } from '@/utils'

const user = inject('$user')
const dayjs = inject('$dayjs')
const route = useRoute()

const tabIndex = ref(route.query.operation === 'Export' ? 1 : 0)
const status = ref(' ')

const STATUS_OPTIONS = [
	{ label: '', value: ' ' },
	{ label: __('Draft'), value: 'Draft' },
	{ label: __('Queued'), value: 'Queued' },
	{ label: __('In Progress'), value: 'In Progress' },
	{ label: __('Completed'), value: 'Completed' },
	{ label: __('Failed'), value: 'Failed' },
	{ label: __('Cancelled'), value: 'Cancelled' },
]

const mailDataExchanges = useList({
	doctype: 'Mail Exchange',
	fields: [
		'name',
		'status',
		'import_format',
		'export_format',
		'export_archive_type',
		'started_at',
	],
	filters: () => {
		const filters: Record<string, string> = {
			user: user.data.name,
			operation: tabIndex.value ? 'Export' : 'Import',
		}
		if (status.value !== ' ') filters.status = status.value
		return filters
	},
	orderBy: 'creation desc',
	transform: (data) =>
		data.map((row) => ({
			...row,
			started_at: row.started_at ? dayjs(row.started_at).format('MMM D, YYYY h:mm A') : '-',
		})),
})

const listColumns = computed(() => {
	const columns = [
		{ label: __('Started'), key: 'started_at' },
		{ label: __('Status'), key: 'status' },
		{
			label: __('Format'),
			key: tabIndex.value ? 'export_format' : 'import_format',
		},
	]
	if (tabIndex.value) columns.push({ label: __('Archive Type'), key: 'export_archive_type' })
	return columns
})

const LIST_OPTIONS = {
	selectable: false,
	getRowRoute: (row) => ({ name: 'MailExchange', params: { id: row.name } }),
	emptyState: { description: __('No mail exchanges found.') },
}

const TABS = [
	{ label: __('Import'), icon: HardDriveDownload, index: 0 },
	{ label: __('Export'), icon: HardDriveUpload, index: 1 },
]
</script>
