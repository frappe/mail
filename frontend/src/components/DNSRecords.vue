<template>
	<div class="space-y-4">
		<div class="space-y-2">
			<h3 class="flex items-center font-medium">
				{{ title }}
				<Badge v-if="badgeLabel" :theme="badgeTheme" :label="badgeLabel" class="ml-2" />
			</h3>
			<p class="text-ink-gray-5 text-sm">{{ description }}</p>
		</div>
		<ListView
			class="max-w-full flex-1"
			:columns="LIST_COLUMNS"
			:rows="records"
			:options="{ selectable: false }"
			row-key="name"
		>
			<ListHeader />
			<ListRows>
				<ListRow v-for="row in records" :key="row.name" :row="row">
					<template #default="{ item }">
						<ListRowItem>
							<Tooltip :text="__('Click to copy')">
								<div class="cursor-copy truncate" @click="copyToClipBoard(item)">
									{{ item }}
								</div>
							</Tooltip>
						</ListRowItem>
					</template>
				</ListRow>
			</ListRows>
		</ListView>
	</div>
</template>

<script setup lang="ts">
import { Badge, ListHeader, ListRow, ListRowItem, ListRows, ListView, Tooltip } from 'frappe-ui'

import { copyToClipBoard } from '@/utils'

const { title, description, records } = defineProps<{
	title: string
	description: string
	records: Record<string, string>[]
	badgeLabel?: string
	badgeTheme?: 'green' | 'red' | 'gray' | 'orange' | 'blue'
}>()

const LIST_COLUMNS = [
	{ label: 'Type', key: 'type', width: '10%' },
	{ label: 'Host', key: 'host', width: '20%' },
	{ label: 'Priority', key: 'priority', width: '10%' },
	{ label: 'TTL (Recommended)', key: 'ttl', width: '10%' },
	{ label: 'Value', key: 'value', width: '50%' },
]
</script>
