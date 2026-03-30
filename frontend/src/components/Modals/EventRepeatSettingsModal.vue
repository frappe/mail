<script setup lang="ts">
import { computed, inject, reactive, watch } from 'vue'
import { Dialog, FormControl } from 'frappe-ui'

import { getRepeatFrequencyOptions } from '@/utils/format'

const show = defineModel<boolean>()
const { startDate, rRule } = defineProps<{ startDate: string; rRule: any }>()
const emit = defineEmits(['updateRecurrenceRule'])

const dayjs = inject('$dayjs')

// Derived from startDate
const startDay = computed(() => dayjs(startDate).format('dd').toLowerCase())
const startWeekNumber = computed(() => Math.ceil(dayjs(startDate).date() / 7))

// ─── State ────────────────────────────────────────────────────────────────────

const getDefaultRepeat = () => ({
	interval: 1,
	frequency: 'daily',
	end: ' ',
	until: dayjs().add(1, 'week').format('YYYY-MM-DD'),
	count: 10,
	byDay: startDay.value ? [{ day: startDay.value }] : ([] as { day: string }[]),
	repeatOn: 'day_of_month',
})

const parseRRule = () => {
	const defaults = getDefaultRepeat()
	const frequency = rRule.frequency ?? defaults.frequency
	const interval = rRule.interval ?? 1

	let end = ' '
	let until = dayjs().add(1, 'week').format('YYYY-MM-DD')
	let count = 10

	if (rRule.until) {
		end = 'On Date'
		until = dayjs(rRule.until).format('YYYY-MM-DD')
	} else if (rRule.count) {
		end = 'After Occurrences'
		count = rRule.count
	}

	let byDay: { day: string }[] = []
	let repeatOn = 'day_of_month'

	if (frequency === 'weekly') {
		byDay = (rRule.byDay ?? []).map((d: any) => ({ day: d.day }))
		if (!byDay.length) byDay = [{ day: startDay.value }]
	} else if (frequency === 'monthly') {
		if (rRule.byMonthDay) {
			const val = Array.isArray(rRule.byMonthDay) ? rRule.byMonthDay[0] : rRule.byMonthDay
			repeatOn = val === -1 ? 'last_day_of_month' : 'day_of_month'
		} else if (rRule.byDay?.length) {
			const entry = rRule.byDay[0]
			repeatOn = entry.nthOfPeriod === -1 ? 'last_day_of_week' : 'day_of_week'
		}
	}

	return { frequency, interval, end, until, count, byDay, repeatOn }
}

const getRepeat = () => (rRule && Object.keys(rRule).length ? parseRRule() : getDefaultRepeat())

const repeat = reactive({ ...getRepeat() })

const toggleDay = (day: string) => {
	const idx = repeat.byDay.findIndex((d) => d.day === day)
	if (idx === -1) repeat.byDay.push({ day })
	else repeat.byDay.splice(idx, 1)
}

// ─── Watches ──────────────────────────────────────────────────────────────────

// Re-sync state when dialog opens
watch(show, (val) => {
	if (val) Object.assign(repeat, getRepeat())
})

// Set default byDay when switching to weekly
watch(
	() => repeat.frequency,
	(freq) => {
		if (freq === 'weekly' && !repeat.byDay.length) repeat.byDay = [{ day: startDay.value }]
	},
)

// ─── Computed ─────────────────────────────────────────────────────────────────

const monthlyRepeatOnOptions = computed(() => {
	const date = dayjs(startDate)
	const dayName = date.format('dddd')
	const ordinals = [__('First'), __('Second'), __('Third'), __('Fourth'), __('Fifth')]
	const daysInMonth = date.daysInMonth()

	const options = [{ label: __('{0} of Month', [date.format('Do')]), value: 'day_of_month' }]

	if (date.date() === daysInMonth)
		options.push({ label: __('Last Day of Month'), value: 'last_day_of_month' })

	options.push({
		label: __('{0} {1} of Month', [ordinals[startWeekNumber.value - 1], dayName]),
		value: 'day_of_week',
	})

	if (startWeekNumber.value === Math.ceil(daysInMonth / 7) || daysInMonth - date.date() < 7)
		options.push({ label: __('Last {0} of Month', [dayName]), value: 'last_day_of_week' })

	return options
})

const recurrenceRule = computed(() => {
	const rule: Record<
		string,
		string | string[] | number | number[] | { day: string; nthOfPeriod?: number }[]
	> = { frequency: repeat.frequency, interval: repeat.interval }

	if (repeat.frequency === 'weekly' && repeat.byDay.length) {
		rule.byDay = repeat.byDay
	} else if (repeat.frequency === 'monthly') {
		const monthlyByDay = {
			day_of_week: [{ day: startDay.value, nthOfPeriod: startWeekNumber.value }],
			last_day_of_week: [{ day: startDay.value, nthOfPeriod: -1 }],
		}
		const monthlyByMonthDay = {
			day_of_month: [dayjs(startDate).date()],
			last_day_of_month: [-1],
		}

		if (repeat.repeatOn in monthlyByDay) rule.byDay = monthlyByDay[repeat.repeatOn]
		else rule.byMonthDay = monthlyByMonthDay[repeat.repeatOn]
	}

	if (repeat.end === 'On Date') rule.until = `${repeat.until}T23:59:59Z`
	else if (repeat.end === 'After Occurrences') rule.count = repeat.count

	return rule
})

// ─── Constants ────────────────────────────────────────────────────────────────

const WEEKDAYS = [
	{ label: __('Sun'), value: 'su' },
	{ label: __('Mon'), value: 'mo' },
	{ label: __('Tue'), value: 'tu' },
	{ label: __('Wed'), value: 'we' },
	{ label: __('Thu'), value: 'th' },
	{ label: __('Fri'), value: 'fr' },
	{ label: __('Sat'), value: 'sa' },
]

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
				emit('updateRecurrenceRule', recurrenceRule.value)
				show.value = false
			},
		},
	],
}
</script>

<template>
	<Dialog v-model="show" :options="DIALOG_OPTIONS">
		<template #body-content>
			<div class="space-y-4">
				<!-- Interval + Frequency -->
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
						label="‎"
						:options="getRepeatFrequencyOptions(repeat.interval)"
						class="w-full"
					/>
				</div>

				<!-- Repeat on days: weekly -->
				<div v-if="repeat.frequency === 'weekly'">
					<label class="text-ink-gray-5 mb-1 block text-xs">
						{{ __('Repeat On Days') }}
					</label>
					<div class="flex w-full overflow-hidden rounded border">
						<button
							v-for="(d, i) in WEEKDAYS"
							:key="d.value"
							type="button"
							class="text-ink-gray-7 h-7 w-full text-xs focus:outline-none"
							:class="{
								'border-r': i !== WEEKDAYS.length - 1,
								'bg-surface-gray-2': !repeat.byDay
									.map((d) => d.day)
									.includes(d.value),
							}"
							@click="toggleDay(d.value)"
						>
							{{ d.label }}
						</button>
					</div>
				</div>

				<!-- Repeat on: monthly -->
				<FormControl
					v-else-if="repeat.frequency === 'monthly'"
					v-model="repeat.repeatOn"
					type="select"
					:label="__('Repeat On')"
					:options="monthlyRepeatOnOptions"
				/>

				<!-- End condition -->
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
