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

const getDefaultEvent = () => {
	const startTime = dayjs(selectedEvent.date).isToday()
		? dayjs().add(1, 'hour').minute(0).second(0).format('HH:mm')
		: '10:00'

	return {
		title: '',
		organizer: user.data.name,
		isAllDay: true,
		repeat: false,
		startDate: dayjs(selectedEvent.date).format('YYYY-MM-DD'),
		startTime,
		endDate: dayjs(selectedEvent.date).format('YYYY-MM-DD'),
		endTime: dayjs(startTime, 'HH:mm').add(30, 'minute').format('HH:mm'),
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

const getEvent = () => {
	const start = dayjs(selectedEvent.calendarEvent?.start)
	const duration = dayjs.duration(selectedEvent.calendarEvent?.duration)
	const end = start.add(duration)
	const isAllDay =
		start.hour() === 0 &&
		start.minute() === 0 &&
		start.second() === 0 &&
		duration.days() > 0 &&
		duration.hours() === 0 &&
		duration.minutes() === 0 &&
		duration.seconds() === 0

	const recurrence_rule = selectedEvent.calendarEvent.recurrence_rule

	const locations = selectedEvent.calendarEvent.locations.length
		? selectedEvent.calendarEvent.locations.map((l) => l._name)
		: ['']

	const alerts = selectedEvent.calendarEvent.alerts?.map((a) => {
		if (a.type === 'OffsetTrigger') {
			const offset = dayjs.duration(a.offset)

			let unit: string
			let number: number
			const d = offset.$d
			if (d.weeks) {
				unit = 'weeks'
				number = Math.abs(d.weeks)
			} else if (d.days) {
				unit = 'days'
				number = Math.abs(d.days)
			} else if (d.hours) {
				unit = 'hours'
				number = Math.abs(d.hours)
			} else {
				unit = 'minutes'
				number = Math.abs(d.minutes)
			}

			return {
				type: a.type,
				action: a.action,
				number,
				unit,
				direction: a.offset.startsWith('-') ? -1 : 1,
				relative_to: a.relative_to,
			}
		} else {
			return {
				type: a.type,
				action: a.action,
				date: dayjs.utc(a.when).format('YYYY-MM-DD'),
				time: dayjs.utc(a.when).format('HH:mm'),
			}
		}
	})

	return {
		title: selectedEvent.calendarEvent.title || '',
		organizer: selectedEvent.calendarEvent.organizer,
		isAllDay,
		repeat: !!recurrence_rule?.frequency,
		startDate: start.format('YYYY-MM-DD'),
		startTime: start.format('HH:mm'),
		endDate: end.format('YYYY-MM-DD'),
		endTime: end.format('HH:mm'),
		free_busy_status: selectedEvent.calendarEvent.free_busy_status,
		privacy: selectedEvent.calendarEvent.privacy,
		locations,
		alerts,
		description: selectedEvent.calendarEvent.description || '',
		participants: [...selectedEvent.calendarEvent.participants],
		recurrence_rule,
	}
}

const event = reactive({})

const duration = computed(() => {
	let duration: string
	if (event.isAllDay) {
		const days = dayjs(event.endDate).diff(dayjs(event.startDate), 'day') + 1
		duration = dayjs.duration({ days }).toISOString()
	} else {
		const start = dayjs(event.startDate + 'T' + event.startTime)
		const end = dayjs(event.endDate + 'T' + event.endTime)
		const diff = dayjs.duration(end.diff(start))
		const hours = Math.floor(diff.asHours())
		const minutes = diff.minutes()
		duration = dayjs.duration({ hours, minutes }).toISOString()
	}
	return duration
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
	const params = {
		user: user.data.name,
		organizer: event.organizer,
		start: dayjs(event.startDate + 'T' + (event.isAllDay ? '00:00' : event.startTime)).format(
			'YYYY-MM-DD[T]HH:mm:ss',
		),
		duration: duration.value,
	}

	if (event.title) params.title = event.title
	if (dayjs && dayjs.tz) params.time_zone = dayjs.tz.guess()
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
			const alert = { action: a.action, type: a.type }
			if (a.type === 'OffsetTrigger')
				return {
					...alert,
					offset: dayjs.duration({ [a.unit]: a.number * a.direction }).toISOString(),
					relative_to: a.relative_to,
				}
			else
				return {
					...alert,
					when: dayjs(a.date + 'T' + a.time).format('YYYY-MM-DD[T]HH:mm:ss'),
				}
		})
	}

	return params
})

const originalEventParams = reactive({})

watch(show, (val) => {
	if (!val) return
	Object.assign(event, isNew.value ? getDefaultEvent() : getEvent())
	Object.assign(originalEventParams, JSON.parse(JSON.stringify(eventParams.value)))
})

const patch = computed(() =>
	Object.fromEntries(
		Object.entries(eventParams.value).filter(
			([key, value]) => JSON.stringify(value) !== JSON.stringify(originalEventParams[key]),
		),
	),
)

const showRepeatSettings = ref(false)

watch(
	() => showRepeatSettings.value,
	(val) => {
		if (!val && !event.recurrence_rule?.frequency) event.repeat = false
	},
)

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

const addParticipant = (email: string) => {
	if (!email?.trim()) return
	if (!/^\S+@\S+\.\S+$/.test(email)) return raiseToast(__('Invalid email address'), 'error')
	if (event.participants.some((p) => p.email.toLowerCase() === email.toLowerCase())) return

	event.participants.push({ email, participation_status: 'NEEDS-ACTION', expect_reply: true })
}

const participantsInput = ref('')

const handleParticipantEnter = (event: Event) => {
	const target = event.target as HTMLInputElement
	const value = target.value.trim()
	if (!value) return
	const emails = value
		.split(',')
		.map((e) => e.trim())
		.filter((e) => e)
	emails.forEach(addParticipant)
	target.value = ''
	participantsInput.value = ''
}

const removeParticipant = (email: string) =>
	(event.participants = event.participants.filter((p) => p.email !== email))

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

const hasParticipantsOtherThanUser = (participants) =>
	participants?.some((p) => identities.data.every((i) => i.email !== p.email)) ?? false

const hadOtherParticipants = computed(() =>
	hasParticipantsOtherThanUser(selectedEvent?.calendarEvent?.participants),
)
const hasOtherParticipants = computed(() => hasParticipantsOtherThanUser(event.participants))

const handleSave = () => {
	if (hadOtherParticipants.value || hasOtherParticipants.value) showSendEmailModal.value = true
	else createOrEditEvent(false)
}

const createOrEditEvent = (sendEmail: boolean) => {
	if (isNew.value)
		toast.promise(createEvent.submit({ sendEmail }), {
			loading: __('Creating event...'),
			success: __('Event created.'),
			error: __('Action failed. Please try again in some time.'),
		})
	else
		toast.promise(
			isUpdateInstance.value && selectedEvent.calendarEvent.recurrence_id
				? editEventInstance.submit({ sendEmail })
				: editEvent.submit({ sendEmail }),
			{
				loading: __('Updating event...'),
				success: __('Event updated.'),
				error: __('Action failed. Please try again in some time.'),
			},
		)
	showSendEmailModal.value = false
}

const mailContacts = createResource({
	url: 'mail.api.contacts.get_contacts',
	makeParams: (text: string) => ({
		filter: { operator: 'OR', conditions: [{ text }, { email: text }] },
	}),
	transform: (data) => data.map((option) => option.email),
})

const debouncedSearch = useDebounceFn((text: string) => text && mailContacts.reload(text), 300)

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
			onClick: () => {
				if (selectedEvent?.calendarEvent?.recurrence_id)
					showRecurringEventModal.value = true
				else handleSave()
			},
		},
	],
}))

const showSendEmailModal = ref(false)

const showSendEmailModalOptions = computed(() => ({
	title: __('Notify Participants'),
	icon: { name: 'bell' },
	message: isNew.value
		? __("Send an email to let attendees know they've been invited?")
		: __('Send an email to let attendees know this event has been updated?'),
}))

const showRecurringEventModal = ref(false)

const SHOW_RECURRING_EVENT_MODAL_OPTIONS = {
	title: __('Update Recurring Event'),
	icon: { name: 'repeat' },
	message: __('Do you want to update just this instance, or all events in the series?'),
}

const isUpdateInstance = ref(true)

const handleSaveRecurringEvent = (updateInstance: boolean) => {
	isUpdateInstance.value = updateInstance
	showRecurringEventModal.value = false
	handleSave()
}

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
</script>

<template>
	<Dialog v-model="show" :disable-outside-click-to-close="true" :options="dialogOptions">
		<template #body-content>
			<div class="grid max-h-[48rem] grid-cols-5 gap-6 overflow-y-auto">
				<div class="col-span-3 space-y-4">
					<h3 class="text-base font-medium">{{ __('Event Details') }}</h3>
					<FormControl
						v-model="event.title"
						:label="__('Title')"
						:placeholder="__('Meeting with Team')"
					/>
					<div class="flex items-center space-x-6">
						<FormControl
							v-model="event.isAllDay"
							:label="__('All Day')"
							type="checkbox"
						/>
						<FormControl
							v-model="event.repeat"
							:label="
								__('Repeat: {0}', [
									event.recurrence_rule?.frequency
										? getRepeatMessage(event.recurrence_rule)
										: __('Off'),
								])
							"
							type="checkbox"
							@update:model-value="
								$event ? (showRepeatSettings = true) : (event.recurrence_rule = {})
							"
						/>
					</div>

					<!-- Date and Time -->
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
				<div class="col-span-2 flex h-full flex-col space-y-4 border-l pl-6">
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
						v-model="participantsInput"
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
	<Dialog v-model="showSendEmailModal" :options="showSendEmailModalOptions">
		<template #actions>
			<div class="flex justify-end space-x-2">
				<Button variant="outline" @click="createOrEditEvent(false)">
					{{ __('Skip') }}
				</Button>
				<Button variant="solid" @click="createOrEditEvent(true)">
					{{ __('Send Email') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>
