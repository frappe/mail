<template>
	<ListView
		class="flex-1 rounded border"
		:class="{ 'min-h-28': !data.length }"
		:columns="REPLY_TO_COLUMNS"
		:rows="data"
		:options="replyToOptions"
		row-key="name"
	>
		<ListHeader class="!mb-0 rounded-b-none border-b bg-transparent" />
		<ListRows>
			<template v-if="data.length">
				<ListRow
					v-for="(row, index) in data"
					:key="row.name"
					v-slot="{ column, item }"
					:row="row"
					:class="{ 'rounded-b-none border-b': index !== data.length - 1 }"
				>
					<div v-if="column.key !== 'delete'" class="text-base">{{ item }}</div>

					<div v-else class="flex">
						<Button variant="ghost" class="ml-auto" @click="emit('delete', index)">
							<template #icon>
								<Trash2 class="text-ink-gray-5 h-4 w-4" />
							</template>
						</Button>
					</div>
				</ListRow>
			</template>
			<ListEmptyState v-else />
		</ListRows>
	</ListView>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Trash2 } from 'lucide-vue-next'
import { Button, ListEmptyState, ListHeader, ListRow, ListRows, ListView } from 'frappe-ui'

const { data, emptyStateDescription } = defineProps<{
	data: { name: string; email: string; display_name?: string }[]
	emptyStateDescription: string
}>()

const emit = defineEmits(['delete'])

const replyToOptions = computed(() => ({
	showTooltip: false,
	selectable: false,
	emptyState: { description: emptyStateDescription },
}))

const REPLY_TO_COLUMNS = [
	{ label: __('Email'), key: 'email' },
	{ label: __('Display Name'), key: 'display_name' },
	{ label: '', key: 'delete' },
]
</script>
