<script setup lang="ts">
import { useTemplateRef, watch } from 'vue'
import { Calendar, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import AppSidebar from '@/components/Calendar/AppSidebar.vue'

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

const events = createResource({
	url: 'mail.api.calendar.get_calendar_events',
	makeParams: () => ({
		from_date: new Date(calendar.value?.currentYear, calendar.value?.currentMonth + 1, 1),
		to_date: new Date(calendar.value?.currentYear, calendar.value?.currentMonth + 1, 0),
	}),
	onSuccess: (data) => console.log('events', data),
	onError: (error) => raiseToast(error.message, 'error'),
})
</script>

<template>
	<div class="flex h-screen min-h-0 w-full min-w-0 flex-col">
		<div class="flex min-h-0 min-w-0 flex-1">
			<AppSidebar />
			<div class="min-h-0 min-w-0 flex-1">
				<Calendar
					ref="calendar"
					@create="(event) => console.log('createEvent', event)"
					@update="(event) => console.log('updateEvent', event)"
					@delete="(eventID) => console.log('deleteEvent', eventID)"
				/>
			</div>
		</div>
	</div>
</template>
