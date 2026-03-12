<script setup lang="ts">
import { computed, inject, reactive, ref, useTemplateRef, watch } from 'vue'
import { Calendar, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import CalendarSidebar from '@/components/CalendarSidebar.vue'
import AddCalendarEventModal from '@/components/Modals/AddCalendarEventModal.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')

const calendar = useTemplateRef('calendar')

watch(
	() => [calendar.value?.currentYear, calendar.value?.currentMonth],
	() => events.reload(),
)

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
		participant: event.organizer,
		venue: event.locations?.[0]?._name || '',
	}
}

const calendars = createResource({
	url: 'mail.api.calendar.get_calendars',
	auto: true,
	onSuccess: (data) => (visibleCalendars.value = data.map((cal) => cal.name)),
	onError: (error) => raiseToast(error.message, 'error'),
})

const visibleCalendars = ref<string[]>([])

const events = createResource({
	url: 'mail.api.calendar.get_calendar_events',
	makeParams: () => ({
		from_date: new Date(calendar.value?.currentYear, calendar.value?.currentMonth, 1),
		to_date: new Date(calendar.value?.currentYear, calendar.value?.currentMonth + 1, 0),
	}),
	transform: (data) => data.map(transformEvent),
	onError: (error) => raiseToast(error.message, 'error'),
})

const deleteEvent = createResource({
	url: 'mail.client.doctype.calendar_event.calendar_event.delete_calendar_events',
	makeParams: (id) => ({ user: user.data.name, ids: [id] }),
	onSuccess: () => raiseToast('Event deleted.', 'success'),
	onError: (error) => raiseToast(error.message, 'error'),
})

const visibleEvents = computed(
	() =>
		events.data?.filter((event) =>
			event.calendars
				.map((c) => c.calendar)
				.some((cal) => visibleCalendars.value.includes(cal)),
		) || [],
)

const showAddEvent = ref(false)

const event = reactive({})

const handleCellClick = (e) => {
	Object.assign(event, e)
	showAddEvent.value = true
}
</script>

<template>
	<div class="flex h-screen min-h-0 w-full min-w-0 flex-col">
		<div class="flex min-h-0 min-w-0 flex-1">
			<CalendarSidebar
				:calendars="calendars?.data || []"
				:visible-calendars
				@update:visible-calendars="
					(name) =>
						visibleCalendars.includes(name)
							? visibleCalendars.splice(visibleCalendars.indexOf(name), 1)
							: visibleCalendars.push(name)
				"
			/>
			<div class="min-h-0 min-w-0 flex-1 p-4">
				<Calendar
					ref="calendar"
					:events="visibleEvents"
					:config="{ isEditMode: true }"
					:on-cell-click="(event) => handleCellClick(event)"
					@update="(event) => console.log('updateEvent', event)"
					@delete="(eventID) => deleteEvent.submit(eventID)"
				/>
			</div>
		</div>
	</div>
	<AddCalendarEventModal
		v-model="showAddEvent"
		:selected-event="event"
		@reload-events="events.reload()"
	/>
</template>
