<script setup lang="ts">
import { computed, inject, reactive, ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { Button, Combobox, Dialog, Dropdown, FormControl, createResource, toast } from 'frappe-ui'

import { getReorderedParticipants, raiseToast } from '@/utils'
import { getRepeatMessage } from '@/utils/format'
import { userStore } from '@/stores/user'
import EventAlertList from '@/components/EventAlertList.vue'
import EventParticipantList from '@/components/EventParticipantList.vue'
import EventRepeatSettingsModal from '@/components/Modals/EventRepeatSettingsModal.vue'

const show = defineModel<boolean>()
const { selectedEvent } = defineProps<{ selectedEvent: any }>()
const emit = defineEmits(['reloadEvents'])

const user = inject('$user')
const dayjs = inject('$dayjs')
const { identities } = userStore()

const isNew = computed(() => !selectedEvent?.calendarEvent)
const showRSVP = computed(() => !isNew.value && selectedEvent.calendarEvent.role !== 'Organizer')

// --- Event initialization ---

const getEventData = () => {
	if (isNew.value) return getDefaultEventData()

	const { calendarEvent: ev } = selectedEvent
	const start = dayjs(ev.start)
	const isAllDay =
		start.hour() === 0 &&
		start.minute() === 0 &&
		start.second() === 0 &&
		dayjs.duration(ev.duration).days() > 0 &&
		dayjs.duration(ev.duration).hours() === 0 &&
		dayjs.duration(ev.duration).minutes() === 0 &&
		dayjs.duration(ev.duration).seconds() === 0
	const end = start.add(dayjs.duration(ev.duration))
	const displayEnd = isAllDay ? end.subtract(1, 'day') : end

	return {
		title: ev.title || '',
		organizer: ev.organizer,
		isAllDay,
		repeat: !!ev.recurrence_rule?.frequency,
		startDate: start.format('YYYY-MM-DD'),
		startTime: start.format('HH:mm'),
		endDate: displayEnd.format('YYYY-MM-DD'),
		endTime: end.format('HH:mm'),
		free_busy_status: ev.free_busy_status,
		privacy: ev.privacy,
		locations: ev.locations.length ? ev.locations.map((l) => l._name) : [''],
		alerts: ev.alerts?.map(parseAlert) ?? [],
		description: ev.description || '',
		participants: [...ev.participants],
		recurrence_rule: ev.recurrence_rule,
	}
}

const getDefaultEventData = () => {
	const startTime = selectedEvent?.time
		? dayjs(selectedEvent.time, 'h a').format('HH:mm')
		: dayjs(selectedEvent.date).isToday()
			? dayjs().add(1, 'hour').startOf('hour').format('HH:mm')
			: '10:00'

	return {
		title: '',
		organizer: user.data.name,
		isAllDay: !selectedEvent?.time,
		repeat: false,
		startDate: dayjs(selectedEvent.date).format('YYYY-MM-DD'),
		startTime,
		endDate: dayjs(selectedEvent.date).format('YYYY-MM-DD'),
		endTime: dayjs(startTime, 'HH:mm').add(1, 'hour').format('HH:mm'),
		locations: [''],
		alerts: [],
		description: '',
		free_busy_status: 'Busy',
		privacy: '',
		participants: [
			{
				email: user.data.name,
				_name: user.data.full_name,
				participation_status: 'ACCEPTED',
			},
		],
		recurrence_rule: {},
	}
}

const event = reactive({})
let originalParams = {}

// --- Computed params ---

const duration = computed(() => {
	if (event.isAllDay) {
		const days = dayjs(event.endDate).diff(dayjs(event.startDate), 'day') + 1
		return dayjs.duration({ days }).toISOString()
	}

	const start = dayjs(`${event.startDate}T${event.startTime}`)
	const end = dayjs(`${event.endDate}T${event.endTime}`)
	const diff = dayjs.duration(end.diff(start))
	const hours = Math.floor(diff.asHours())
	const minutes = diff.minutes()
	return dayjs.duration({ hours, minutes }).toISOString()
})

const participants = computed(() =>
	getReorderedParticipants(
		event.participants,
		event.organizer,
		selectedEvent.calendarEvent?.participants,
	),
)

const userParticipant = computed(() =>
	participants.value.find((p) => identities.data.some((id) => id.email === p.email)),
)

const eventParams = computed(() => {
	const params: Record<string, any> = {
		user: user.data.name,
		organizer: event.organizer,
		start: dayjs(`${event.startDate}T${event.isAllDay ? '00:00' : event.startTime}`).format(
			'YYYY-MM-DD[T]HH:mm:ss',
		),
		duration: duration.value,
	}

	if (selectedEvent.calendarEvent?.recurrence_id && !isUpdateInstance.value) {
		params.start = selectedEvent.calendarEvent.master_start
	}

	if (event.title) params.title = event.title
	if (dayjs?.tz) params.time_zone = dayjs.tz.guess()
	if (event.recurrence_rule && Object.keys(event.recurrence_rule).length)
		params.recurrence_rule = event.recurrence_rule
	if (event.privacy) params.privacy = event.privacy
	if (event.free_busy_status) params.free_busy_status = event.free_busy_status
	if (event.description) params.description = event.description
	if (event.locations?.some((l) => l?.trim()))
		params.locations = event.locations.filter((l) => l?.trim()).map((name) => ({ name }))
	if (event.participants?.length) params.participants = event.participants
	if (event.alerts?.length) {
		params.alerts = event.alerts.map((a) => {
			const base = { action: a.action, type: a.type }
			if (a.type === 'AbsoluteTrigger')
				return {
					...base,
					when: dayjs(`${a.date}T${a.time}`).format('YYYY-MM-DD[T]HH:mm:ss'),
				}

			return {
				...base,
				offset: dayjs.duration({ [a.unit]: a.number * a.direction }).toISOString(),
				relative_to: a.relative_to,
			}
		})
	}

	return params
})

const patch = computed(() =>
	Object.fromEntries(
		[...new Set([...Object.keys(eventParams.value), ...Object.keys(originalParams)])]
			.filter(
				(k) => JSON.stringify(eventParams.value[k]) !== JSON.stringify(originalParams[k]),
			)
			.map((k) => [k, eventParams.value[k]]),
	),
)

// --- Helpers ---

const parseAlert = (a: any) => {
	if (a.type === 'AbsoluteTrigger')
		return {
			type: a.type,
			action: a.action,
			date: dayjs.utc(a.when).format('YYYY-MM-DD'),
			time: dayjs.utc(a.when).format('HH:mm'),
		}

	const d = dayjs.duration(a.offset).$d
	const units = ['weeks', 'days', 'hours', 'minutes']
	const unit = units.find((u) => d[u]) ?? 'minutes'
	const number = d[unit]

	return {
		type: a.type,
		action: a.action,
		number: Math.abs(number),
		unit,
		direction: a.offset.startsWith('-') ? -1 : 1,
		relative_to: a.relative_to,
	}
}

const hasParticipantsOtherThanUser = (participants: any[]) =>
	participants?.some((p) => identities.data.every((i) => i.email !== p.email)) ?? false

// --- Watchers ---

watch(show, (val) => {
	if (!val) return
	Object.assign(event, getEventData())
	originalParams = JSON.parse(JSON.stringify(eventParams.value))
})

const showRepeatSettings = ref(false)
watch(showRepeatSettings, (val) => {
	if (!val && !event.recurrence_rule?.frequency) event.repeat = false
})

// --- Participants ---

const addParticipant = (email: string) => {
	if (!email?.trim()) return
	if (!/^\S+@\S+\.\S+$/.test(email)) return raiseToast(__('Invalid email address'), 'error')
	if (event.participants.some((p) => p.email.toLowerCase() === email.toLowerCase())) return
	event.participants.push({ email, participation_status: 'NEEDS-ACTION', expect_reply: true })
}

const handleParticipantEnter = (e: Event) => {
	const value = (e.target as HTMLInputElement).value.trim()
	if (!value) return
	value
		.split(',')
		.map((s) => s.trim())
		.filter(Boolean)
		.forEach(addParticipant)
	;(e.target as HTMLInputElement).value = ''
}

const removeParticipant = (email: string) =>
	(event.participants = event.participants.filter((p) => p.email !== email))

// --- Save logic ---

const handleSuccess = () => {
	show.value = false
	emit('reloadEvents')
}

const createEvent = createResource({
	url: 'mail.client.doctype.calendar_event.calendar_event.add_calendar_event',
	makeParams: ({ sendEmail }: { sendEmail: boolean }) => ({
		...eventParams.value,
		send_scheduling_messages: sendEmail,
	}),
	onSuccess: handleSuccess,
})

const editEventInstance = createResource({
	url: 'mail.client.doctype.calendar_event.calendar_event.update_calendar_event_instance',
	makeParams: ({ sendEmail }: { sendEmail: boolean }) => ({
		user: user.data.name,
		master_id: selectedEvent.calendarEvent.master_id,
		recurrence_id: selectedEvent.calendarEvent.recurrence_id,
		patch: patch.value,
		send_scheduling_messages: sendEmail,
	}),
	onSuccess: handleSuccess,
})

const editEvent = createResource({
	url: 'mail.client.doctype.calendar_event.calendar_event.update_calendar_event',
	makeParams: ({ sendEmail }: { sendEmail: boolean }) => ({
		id: selectedEvent.calendarEvent.master_id,
		uid: selectedEvent.calendarEvent.uid,
		...eventParams.value,
		send_scheduling_messages: sendEmail,
	}),
	onSuccess: handleSuccess,
})

const isUpdateInstance = ref(false)

const submitEvent = (sendEmail: boolean) => {
	const isInstance = isUpdateInstance.value && selectedEvent.calendarEvent?.recurrence_id
	const resource = isNew.value ? createEvent : isInstance ? editEventInstance : editEvent
	const messages = isNew.value
		? { loading: __('Creating event...'), success: __('Event created.') }
		: { loading: __('Updating event...'), success: __('Event updated.') }

	toast.promise(resource.submit({ sendEmail }), {
		...messages,
		error: __('Action failed. Please try again in some time.'),
	})
	showNotifyParticipantsModal.value = false
}

const showNotifyParticipantsModal = ref(false)
const showRecurringEventModal = ref(false)

const handleSave = () => {
	const needsEmail =
		hasParticipantsOtherThanUser(selectedEvent?.calendarEvent?.participants) ||
		hasParticipantsOtherThanUser(event.participants)
	if (needsEmail) showNotifyParticipantsModal.value = true
	else submitEvent(false)
}

const handleSaveRecurringEvent = (updateInstance: boolean) => {
	isUpdateInstance.value = updateInstance
	showRecurringEventModal.value = false
	handleSave()
}

const shouldShowRecurringEventModal = computed(
	() =>
		selectedEvent?.calendarEvent?.recurrence_id &&
		!Object.keys(patch.value).includes('recurrence_rule'),
)

// --- Alerts ---

const addAlertOptions = computed(() => [
	{
		label: __('Relative to event'),
		onClick: () =>
			event.alerts.push({
				type: 'OffsetTrigger',
				action: 'Display',
				number: 10,
				unit: 'minutes',
				direction: -1,
				relative_to: 'Start',
			}),
	},
	{
		label: __('On specific date'),
		onClick: () =>
			event.alerts.push({
				type: 'AbsoluteTrigger',
				action: 'Display',
				date: dayjs(event.startDate).subtract(1, 'day').format('YYYY-MM-DD'),
				time: '09:00',
			}),
	},
])

// --- Contacts search ---

const mailContacts = createResource({
	url: 'mail.api.contacts.get_contacts',
	makeParams: (text: string) => ({
		filter: { operator: 'OR', conditions: [{ text }, { email: text }] },
	}),
	transform: (data) => data.map((o) => o.email),
})

const debouncedSearch = useDebounceFn((text: string) => text && mailContacts.reload(text), 300)

// --- Dialog options ---

const dialogOptions = computed(() => ({
	title: isNew.value ? __('Add Event') : __('Edit Event'),
	size: '5xl',
	actions: [
		{
			label: __('Save'),
			variant: 'solid',
			disabled:
				createEvent.loading ||
				editEvent.loading ||
				editEventInstance.loading ||
				(!isNew.value && !Object.keys(patch.value).length),
			onClick: () =>
				shouldShowRecurringEventModal.value
					? (showRecurringEventModal.value = true)
					: handleSave(),
		},
	],
}))

const RSVP_OPTIONS = [
	{ label: __(' '), value: 'NEEDS-ACTION' },
	{ label: __('Yes'), value: 'ACCEPTED' },
	{ label: __('Maybe'), value: 'TENTATIVE' },
	{ label: __('No'), value: 'DECLINED' },
]

const AVAILABILITY_OPTIONS = [
	{ label: __('Free'), value: 'Free' },
	{ label: __('Busy'), value: 'Busy' },
]

const VISIBILITY_OPTIONS = [
	{ label: __('Public'), value: 'Public' },
	{ label: __('Private'), value: 'Private' },
]

const showNotifyParticipantsOptions = computed(() => ({
	title: __('Notify Participants'),
	icon: { name: 'bell' },
	message: isNew.value
		? __("Send an email to let attendees know they've been invited?")
		: __('Send an email to let attendees know this event has been updated?'),
}))

const SHOW_RECURRING_EVENT_MODAL_OPTIONS = {
	title: __('Update Recurring Event'),
	icon: { name: 'repeat' },
	message: __('Do you want to update just this instance, or all events in the series?'),
}
</script>

<template>
	<Dialog v-model="show" :disable-outside-click-to-close="true" :options="dialogOptions">
		<template #body-content>
			<div class="grid max-h-[48rem] grid-cols-11 gap-6 overflow-y-auto">
				<div class="col-span-7 space-y-4">
					<h3 class="text-base font-medium">{{ __('Event Details') }}</h3>
					<!-- Title -->
					<FormControl
						v-model="event.title"
						:label="__('Title')"
						:placeholder="__('Meeting with Team')"
					/>

					<!-- Date and Time -->
					<FormControl v-model="event.isAllDay" :label="__('All Day')" type="checkbox" />
					<div class="flex space-x-4">
						<FormControl
							v-model="event.startDate"
							type="date"
							:label="__('Start Date')"
							class="w-full"
						/>
						<FormControl
							v-if="!event.isAllDay"
							v-model="event.startTime"
							type="time"
							:label="__('Start Time')"
							class="w-full"
						/>
					</div>
					<div class="flex space-x-4">
						<FormControl
							v-model="event.endDate"
							type="date"
							:label="__('End Date')"
							class="w-full"
						/>
						<FormControl
							v-if="!event.isAllDay"
							v-model="event.endTime"
							type="time"
							:label="__('End Time')"
							class="w-full"
						/>
					</div>

					<!-- Repeat -->
					<div class="flex items-center space-x-3">
						<FormControl
							v-model="event.repeat"
							:label="
								event.recurrence_rule?.frequency
									? __('Repeat: {0}', [getRepeatMessage(event.recurrence_rule)])
									: __('Repeat')
							"
							type="checkbox"
							@update:model-value="
								$event ? (showRepeatSettings = true) : (event.recurrence_rule = {})
							"
						/>
						<span
							v-if="event.recurrence_rule?.frequency"
							class="text-ink-gray-4 cursor-pointer text-base hover:underline"
							@click="showRepeatSettings = true"
						>
							{{ __('Edit') }}
						</span>
					</div>

					<!-- Locations -->
					<div class="space-y-2">
						<div v-for="(_, i) in event.locations" :key="i" class="flex space-x-2">
							<FormControl
								v-model="event.locations[i]"
								:label="
									i === 0
										? event.locations.length > 1
											? __('Locations')
											: __('Location')
										: ''
								"
								:placeholder="__('Meeting location {0}', [i + 1])"
								class="w-full"
							/>
							<Button
								v-if="
									event.locations.length === i + 1 && event.locations.length < 3
								"
								icon="plus"
								class="mt-auto"
								@click="event.locations.push('')"
							/>
							<Button
								v-else
								icon="x"
								class="mt-auto"
								@click="event.locations.splice(i, 1)"
							/>
						</div>
					</div>

					<!-- Alerts -->
					<div class="space-y-2">
						<EventAlertList v-model:alerts="event.alerts" />
						<Dropdown
							v-if="event.alerts.length < 3"
							:button="{ label: __('Add Alert') }"
							:options="addAlertOptions"
						/>
					</div>

					<!-- Availability and Privacy -->
					<div class="flex space-x-4">
						<FormControl
							v-model="event.free_busy_status"
							type="select"
							:label="__('Availability')"
							:options="AVAILABILITY_OPTIONS"
							class="w-full"
						/>
						<FormControl
							v-model="event.privacy"
							type="select"
							:label="__('Visibility')"
							:options="VISIBILITY_OPTIONS"
							class="w-full"
						/>
					</div>

					<!-- Description -->
					<FormControl
						v-model="event.description"
						:label="__('Description')"
						type="textarea"
						:placeholder="__('Event description')"
					/>
				</div>
				<div class="col-span-4 flex h-full flex-col space-y-4 border-l pl-6">
					<!-- RSVP -->
					<template v-if="showRSVP">
						<h3 class="text-base font-medium">{{ __('RSVP') }}</h3>
						<FormControl
							v-model="userParticipant.participation_status"
							type="select"
							:label="__('Are you attending?')"
							:options="RSVP_OPTIONS"
							class="w-full"
						/>
					</template>

					<!-- Participants -->
					<h3 class="text-base font-medium">{{ __('Participants') }}</h3>
					<Combobox
						:options="mailContacts?.data || []"
						:placeholder="__('Enter participants')"
						@input="debouncedSearch($event)"
						@keyup.enter="handleParticipantEnter($event)"
					/>
					<div class="max-h-[32rem] space-y-4 overflow-y-auto">
						<EventParticipantList
							:participants
							@remove-participant="removeParticipant"
						/>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
	<EventRepeatSettingsModal
		v-model="showRepeatSettings"
		:start-date="event?.startDate"
		:r-rule="event?.recurrence_rule"
		@update-recurrence-rule="(val) => (event.recurrence_rule = val)"
	/>
	<Dialog v-model="showRecurringEventModal" :options="SHOW_RECURRING_EVENT_MODAL_OPTIONS">
		<template #actions>
			<div class="flex justify-end space-x-2">
				<Button @click="handleSaveRecurringEvent(false)">{{ __('Entire series') }}</Button>
				<Button variant="solid" @click="handleSaveRecurringEvent(true)">
					{{ __('This instance') }}
				</Button>
			</div>
		</template>
	</Dialog>
	<Dialog v-model="showNotifyParticipantsModal" :options="showNotifyParticipantsOptions">
		<template #actions>
			<div class="flex justify-end space-x-2">
				<Button variant="outline" @click="submitEvent(false)"> {{ __('Skip') }} </Button>
				<Button variant="solid" @click="submitEvent(true)">
					{{ __('Send Email') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>
