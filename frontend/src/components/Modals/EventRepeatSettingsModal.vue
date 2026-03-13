<template>
	<Dialog v-model="show" :options="DIALOG_OPTIONS">
		<template #body-content>
			<div class="space-y-4">
				<div class="flex space-x-4">
					<FormControl
						v-model="repeat.interval"
						:label="__('Repeat Every')"
						type="number"
						class="w-full"
					/>
					<FormControl
						v-model="repeat.frequency"
						type="select"
						:label="__('‎')"
						:options="getRepeatFrequencyOptions(repeat.interval)"
						class="w-full"
					/>
				</div>
				<FormControl
					v-model="repeat.end"
					type="select"
					:label="__('End')"
					:options="END_OPTIONS"
				/>
				<FormControl
					v-if="repeat.end === 'On Date'"
					v-model="repeat.until"
					type="date"
					:label="__('End Date')"
				/>
				<FormControl
					v-else-if="repeat.end === 'After Occurrences'"
					v-model="repeat.count"
					type="number"
					:label="__('Total Occurrences')"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, inject, reactive, watch } from 'vue'
import { Dialog, FormControl } from 'frappe-ui'

import { getRepeatFrequencyOptions } from '@/utils'

const show = defineModel<boolean>()

const emit = defineEmits(['updateRecurrenceRule'])

const dayjs = inject('$dayjs')

const defaultRepeat = {
	interval: 1,
	frequency: 'daily',
	end: ' ',
	until: dayjs().add(1, 'week').format('YYYY-MM-DD'),
	count: 10,
}

const repeat = reactive({ ...defaultRepeat })

const reccurrenceRule = computed(() => {
	const rule = { frequency: repeat.frequency, interval: repeat.interval }
	if (repeat.end === 'On Date') rule.until = repeat.until
	else if (repeat.end === 'After Occurrences') rule.count = repeat.count
	return rule
})

watch(show, (val) => {
	if (val) Object.assign(repeat, defaultRepeat)
})

const END_OPTIONS = [
	{ label: __('Never'), value: ' ' },
	{ label: __('On Date'), value: 'On Date' },
	{ label: __('After Occurrences'), value: 'After Occurrences' },
]

const DIALOG_OPTIONS = {
	title: __('Repeat Settings'),
	actions: [
		{
			label: __('Apply'),
			variant: 'solid',
			onClick: () => {
				emit('updateRecurrenceRule', reccurrenceRule.value)
				show.value = false
			},
		},
	],
}
</script>
