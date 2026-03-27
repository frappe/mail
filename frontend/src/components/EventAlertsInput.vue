<script setup lang="ts">
import { Button, FormControl } from 'frappe-ui'

const { alerts } = defineProps<{ alerts: any[] }>()

const emit = defineEmits(['update:alerts'])

const updateAlert = (i: number, field: string, value: any) => {
	const updated = alerts.map((a, idx) => (idx === i ? { ...a, [field]: value } : a))
	emit('update:alerts', updated)
}

const removeAlert = (i: number) => {
	const updated = alerts.filter((_, idx) => idx !== i)
	emit('update:alerts', updated)
}

const ALERT_ACTION_OPTIONS = [
	{ label: __('Screen Pop-up'), value: 'Display' },
	{ label: __('Email Notice'), value: 'Email' },
	{ label: __('Sound Alert'), value: 'Audio' },
]

const UNIT_OPTIONS = [
	{ label: __('Minutes'), value: 'minutes' },
	{ label: __('Hours'), value: 'hours' },
	{ label: __('Days'), value: 'days' },
	{ label: __('Weeks'), value: 'weeks' },
]

const DIRECTION_OPTIONS = [
	{ label: __('Before'), value: -1 },
	{ label: __('After'), value: 1 },
]

const RELATIVE_TO_OPTIONS = [
	{ label: __('Start'), value: 'Start' },
	{ label: __('End'), value: 'End' },
]
</script>

<template>
	<div v-for="(alert, i) in alerts" :key="i" class="flex space-x-2">
		<FormControl
			:model-value="alert.action"
			:label="i === 0 ? (alerts.length > 1 ? __('Alerts') : __('Alert')) : ''"
			type="select"
			:options="ALERT_ACTION_OPTIONS"
			class="w-40 shrink-0"
			@update:model-value="updateAlert(i, 'action', $event)"
		/>
		<template v-if="alert.type === 'OffsetTrigger'">
			<FormControl
				:model-value="alert.number"
				type="number"
				class="mt-auto w-16 shrink-0"
				@update:model-value="updateAlert(i, 'number', $event)"
			/>
			<FormControl
				:model-value="alert.unit"
				type="select"
				:options="UNIT_OPTIONS"
				class="mt-auto w-full"
				@update:model-value="updateAlert(i, 'unit', $event)"
			/>
			<FormControl
				:model-value="alert.direction"
				type="select"
				:options="DIRECTION_OPTIONS"
				class="mt-auto w-full"
				@update:model-value="updateAlert(i, 'direction', $event)"
			/>
			<FormControl
				:model-value="alert.relative_to"
				type="select"
				:options="RELATIVE_TO_OPTIONS"
				class="mt-auto w-full"
				@update:model-value="updateAlert(i, 'relative_to', $event)"
			/>
		</template>
		<template v-else>
			<span class="text-ink-gray-8 mb-1.5 mt-auto text-base">{{ __('on') }}</span>
			<FormControl
				:model-value="alert.date"
				type="date"
				class="mt-auto w-full"
				@update:model-value="updateAlert(i, 'date', $event)"
			/>
			<span class="text-ink-gray-8 mb-1.5 mt-auto text-base">{{ __('at') }}</span>
			<FormControl
				:model-value="alert.time"
				type="time"
				class="mt-auto w-full"
				@update:model-value="updateAlert(i, 'time', $event)"
			/>
		</template>
		<Button icon="x" class="mt-auto" @click="removeAlert(i)" />
	</div>
</template>
