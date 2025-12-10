<template>
	<DashboardCard :title @action="emit('add')">
		<ListView
			:columns="[{ label: columnLabel, key: 'value', showTooltip: false }]"
			:rows="rows"
			row-key="value"
			:options="{ emptyState: { title: '', description: __('No rows.') } }"
			class="flex-1 overflow-auto p-4"
		>
			<ListHeader />
			<ListRows v-if="rows" />
			<ListEmptyState v-else />
			<ListSelectBanner>
				<template #actions="{ selections, unselectAll }">
					<Button
						variant="ghost"
						:label="__('Remove')"
						theme="red"
						@click="
							() => {
								emit('remove', selections)
								unselectAll()
							}
						"
					/>
				</template>
			</ListSelectBanner>
		</ListView>
	</DashboardCard>
</template>

<script setup lang="ts">
import {
	Button,
	ListEmptyState,
	ListHeader,
	ListRows,
	ListSelectBanner,
	ListView,
} from 'frappe-ui'

import DashboardCard from '@/components/DashboardCard.vue'

defineProps<{ rows: { value: string }[]; title: string; columnLabel: string }>()

const emit = defineEmits(['add', 'remove'])
</script>
