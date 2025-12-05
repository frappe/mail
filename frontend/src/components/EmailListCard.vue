<template>
	<div class="flex h-80 shrink-0 flex-col rounded-md border">
		<div class="flex items-center justify-between border-b px-4 py-2.5">
			<h2>{{ title }}</h2>
			<Button variant="ghost" :label="__('Add')" icon-left="plus" @click="emit('add')" />
		</div>
		<ListView
			:columns="[{ label: columnLabel, key: 'value' }]"
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
	</div>
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

defineProps<{
	rows: { value: string }[]
	title: string
	columnLabel: string
}>()

const emit = defineEmits(['add', 'remove'])
</script>
