<script setup lang="ts">
import { computed, inject, onMounted, reactive, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Calendar, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'
import CalendarSidebar from '@/components/CalendarSidebar.vue'
import EventPopoverContent from '@/components/EventPopoverContent.vue'
import EventModal from '@/components/Modals/EventModal.vue'

const dayjs = inject('$dayjs')

const { identities } = userStore()

const route = useRoute()
const router = useRouter()

const calendar = useTemplateRef('calendar')

watch(
	() => [calendar.value?.currentYear, calendar.value?.currentMonth],
	() => events.reload(),
)

watch(
	() => calendar.value?.activeView,
	(view) => router.replace({ query: { ...route.query, view } }),
)

onMounted(() => {
	if (route.query.view) calendar.value.activeView = route.query.view.toString()
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
		participant: event.organizer,
		venue: event.locations?.[0]?._name || '',
		role: getEventRole(event),
	}
}

const getEventRole = (event) => {
	if (identities.data.some((id) => id.email === event.organizer.replace('mailto:', '')))
		return 'Organizer'
	if (
		identities.data.some((id) =>
			event.participants?.some((p) => p.email.replace('mailto:', '') === id.email),
		)
	)
		return 'Attendee'
	return 'Viewer'
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
	makeParams: () => {
		const date = dayjs().year(calendar.value?.currentYear).month(calendar.value?.currentMonth)
		return {
			from_date: date.startOf('month').subtract(37, 'day').toDate(),
			to_date: date.endOf('month').add(37, 'day').toDate(),
			time_zone: dayjs.tz.guess(),
		}
	},
	transform: (data) => data.map(transformEvent),
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

const showEditEvent = ref(false)

const event = reactive({})

const handleOpenEvent = (e) => {
	Object.assign(event, e)
	showEditEvent.value = true
}

watch(
	() => showEditEvent.value,
	(val) => {
		if (!val) Object.keys(event).forEach((key) => delete event[key])
	},
)
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
					:on-dbl-click="(event) => handleOpenEvent(event)"
					:on-cell-click="(event) => handleOpenEvent(event)"
				>
					<template #event-popover-content="{ calendarEvent, close }">
						<EventPopoverContent
							:calendar-event
							:close
							@edit="handleOpenEvent({ calendarEvent })"
							@reload-events="events.reload()"
						/>
					</template>
				</Calendar>
			</div>
		</div>
	</div>
	<EventModal v-model="showEditEvent" :selected-event="event" @reload-events="events.reload()" />
</template>
