<script setup lang="ts">
import { inject, useTemplateRef, watch } from 'vue'
import { Calendar, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import CalendarSidebar from '@/components/CalendarSidebar.vue'

const dayjs = inject('$dayjs')

const calendar = useTemplateRef('calendar')

watch(
	() => [calendar.value?.currentYear, calendar.value?.currentMonth],
	() => events.reload(),
)

const calendars = createResource({
	url: 'mail.api.calendar.get_calendars',
	auto: true,
	onError: (error) => raiseToast(error.message, 'error'),
})

const transformEvent = (event) => {
	const start = dayjs(event.start)
	const durationMatch = /PT(?:(\d+)H)?(?:(\d+)M)?/.exec(event.duration || '')
	const hours = durationMatch && durationMatch[1] ? parseInt(durationMatch[1]) : 0
	const minutes = durationMatch && durationMatch[2] ? parseInt(durationMatch[2]) : 0
	const end = start.add(hours, 'hour').add(minutes, 'minute')
	return {
		...event,
		fromDate: start.format('YYYY-MM-DD'),
		toDate: end.format('YYYY-MM-DD'),
		fromTime: start.format('HH:mm'),
		toTime: end.format('HH:mm'),
	}
}

const events = createResource({
	url: 'mail.api.calendar.get_calendar_events',
	makeParams: () => ({
		from_date: new Date(calendar.value?.currentYear, calendar.value?.currentMonth, 1),
		to_date: new Date(calendar.value?.currentYear, calendar.value?.currentMonth + 1, 0),
	}),
	transform: (data) => data.map(transformEvent),
	onError: (error) => raiseToast(error.message, 'error'),
})
</script>

<template>
	<div class="flex h-screen min-h-0 w-full min-w-0 flex-col">
		<div class="flex min-h-0 min-w-0 flex-1">
			<CalendarSidebar />
			<div class="min-h-0 min-w-0 flex-1 p-4">
				<Calendar
					ref="calendar"
					:events="events.data"
					@create="(event) => console.log('createEvent', event)"
					@update="(event) => console.log('updateEvent', event)"
					@delete="(eventID) => console.log('deleteEvent', eventID)"
				/>
			</div>
		</div>
	</div>
</template>
