<script setup lang="ts">
import { computed, inject, reactive, ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import {
	Button,
	Combobox,
	Dialog,
	FormControl,
	ListHeader,
	ListRows,
	ListSelectBanner,
	ListView,
	createResource,
} from 'frappe-ui'

import { getRepeatFrequencyOptions, raiseToast } from '@/utils'
import EventRepeatSettingsModal from '@/components/Modals/EventRepeatSettingsModal.vue'

const show = defineModel<boolean>()

const { selectedEvent } = defineProps<{ selectedEvent: any }>()

const emit = defineEmits(['reload-events'])

const user = inject('$user')
const dayjs = inject('$dayjs')

const getDefaultEvent = () => {
	const startTime = dayjs(selectedEvent.date).isToday()
		? dayjs().add(1, 'hour').minute(0).second(0).format('HH:mm')
		: '10:00'

	return {
		title: '',
		isAllDay: true,
		repeat: false,
		startDate: dayjs(selectedEvent.date).format('YYYY-MM-DD'),
		startTime,
		endDate: dayjs(selectedEvent.date).format('YYYY-MM-DD'),
		endTime: dayjs(startTime, 'HH:mm').add(30, 'minute').format('HH:mm'),
		location: '',
		description: '',
		free_busy_status: 'Busy',
		privacy: '',
		participants: [] as Array<{ email: string }>,
		send_scheduling_messages: false,
		recurrence_rule: {},
	}
}

const getEvent = () => {
	const start = dayjs(selectedEvent.calendarEvent?.start)
	const duration = dayjs.duration(selectedEvent.calendarEvent?.duration)
	const end = start.add(duration)
	const isAllDay =
		duration.days() > 0 &&
		duration.hours() === 0 &&
		duration.minutes() === 0 &&
		duration.seconds() === 0

	const recurrence_rule = JSON.parse(selectedEvent.calendarEvent.recurrence_rule)

	return {
		title: selectedEvent.calendarEvent.title || '',
		isAllDay,
		repeat: !!recurrence_rule?.frequency,
		startDate: start.format('YYYY-MM-DD'),
		startTime: start.format('HH:mm'),
		endDate: end.format('YYYY-MM-DD'),
		endTime: end.format('HH:mm'),
		free_busy_status: selectedEvent.calendarEvent.free_busy_status,
		privacy: selectedEvent.calendarEvent.privacy,
		location: selectedEvent.calendarEvent.locations?.[0]?._name || '',
		description: selectedEvent.calendarEvent.description || '',
		participants: selectedEvent.calendarEvent.participants || [],
		recurrence_rule,
	}
}

const event = reactive({})

watch(show, (val) => {
	if (val) Object.assign(event, selectedEvent?.calendarEvent ? getEvent() : getDefaultEvent())
})

const showRepeatSettings = ref(false)

watch(
	() => showRepeatSettings.value,
	(val) => {
		if (!val && !event.recurrence_rule?.frequency) event.repeat = false
	},
)

const repeatMessage = computed(() => {
	if (!event.recurrence_rule?.frequency) return ''
	const message = __('Every {0} {1}', [
		event.recurrence_rule.interval === 1 ? '' : event.recurrence_rule.interval,
		getRepeatFrequencyOptions(event.recurrence_rule.interval)
			.find((option) => option.value === event.recurrence_rule.frequency)
			?.label.toLowerCase(),
	])

	if (event.recurrence_rule?.until)
		return __('{0} until {1}', [
			message,
			dayjs(event.recurrence_rule.until).format('MMM DD, YYYY'),
		])

	if (event.recurrence_rule?.count)
		return __('{0}, {1} occurrences', [message, event.recurrence_rule.count])

	return message
})

const addParticipant = (email: string) => {
	email = email.trim()
	if (!email) return
	if (!/^\S+@\S+\.\S+$/.test(email)) {
		raiseToast(__('Invalid email address'), 'error')
		return
	}
	if (event.participants.some((p) => p.email.toLowerCase() === email.toLowerCase())) return
	event.participants.push({ email })
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

const createEvent = createResource({
	url: 'mail.client.doctype.calendar_event.calendar_event.add_calendar_event',
	makeParams: () => {
		const start = dayjs(event.startDate + 'T' + event.startTime)
		let duration: string
		if (event.isAllDay) {
			const days = dayjs(event.endDate).diff(dayjs(event.startDate), 'day') + 1
			duration = dayjs.duration({ days }).toISOString()
		} else {
			const end = dayjs(event.endDate + 'T' + event.endTime)
			const diff = dayjs.duration(end.diff(start))
			const hours = Math.floor(diff.asHours())
			const minutes = diff.minutes()
			duration = dayjs.duration({ hours, minutes }).toISOString()
		}

		return {
			user: user.data.name,
			organizer: user.data.name,
			title: event.title,
			start: start.format('YYYY-MM-DD[T]HH:mm:ss'),
			duration,
			locations: [{ name: event.location }],
			free_busy_status: event.free_busy_status,
			privacy: event.privacy,
			participants: event.participants,
			description: event.description,
			send_scheduling_messages: event.send_scheduling_messages,
			recurrence_rule: event.recurrence_rule,
			time_zone: dayjs.tz.guess(),
		}
	},
	onSuccess: () => {
		raiseToast(__('Event created.'), 'success')
		show.value = false
		emit('reload-events')
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

const mailContacts = createResource({
	url: 'mail.api.contacts.get_contacts',
	makeParams: (text: string) => ({
		filter: { operator: 'OR', conditions: [{ text }, { email: text }] },
	}),
	transform: (data) => data.map((option) => option.email),
})

const debouncedSearch = useDebounceFn((text: string) => text && mailContacts.reload(text), 300)

const dialogOptions = computed(() => ({
	title: selectedEvent?.calendarEvent ? __('Edit Event') : __('Add Event'),
	size: '2xl',
	actions: [{ label: __('Save'), variant: 'solid', onClick: () => createEvent.submit() }],
}))

const AVAILABILITY_OPTIONS = [
	{ label: __('Free'), value: 'Free' },
	{ label: __('Busy'), value: 'Busy' },
]

const VISIBILITY_OPTIONS = [
	{ label: __('Public'), value: 'Public' },
	{ label: __('Private'), value: 'Private' },
]

const PARTICIPANT_COLUMNS = [{ label: __('Email'), key: 'email' }]
</script>

<template>
	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="event.title"
					:label="__('Title')"
					:placeholder="__('Meeting with Team')"
				/>
				<div class="flex items-center space-x-6">
					<FormControl v-model="event.isAllDay" :label="__('All Day')" type="checkbox" />
					<FormControl
						v-model="event.repeat"
						:label="__('Repeat: {0}', [repeatMessage || __('Off')])"
						type="checkbox"
						@update:model-value="
							$event ? (showRepeatSettings = true) : (event.recurrence_rule = {})
						"
					/>
				</div>
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
				<FormControl
					v-model="event.location"
					:label="__('Location')"
					:placeholder="__('Meeting location')"
				/>
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
				<FormControl
					v-model="event.description"
					:label="__('Description')"
					type="textarea"
					:placeholder="__('Event description')"
				/>

				<hr />

				<h3 class="text-base font-medium">{{ __('Participants') }}</h3>

				<Combobox
					v-model="participantsInput"
					:options="mailContacts?.data || []"
					:placeholder="__('Enter participants')"
					@input="debouncedSearch($event)"
					@keyup.enter="handleParticipantEnter($event)"
				/>

				<ListView
					:columns="PARTICIPANT_COLUMNS"
					:rows="event.participants"
					row-key="email"
					class="max-h-32"
				>
					<ListHeader v-if="event.participants.length" />
					<ListRows />

					<ListSelectBanner>
						<template #actions="{ selections, unselectAll }">
							<Button
								variant="ghost"
								theme="red"
								:label="__('Remove')"
								@click="
									() => {
										event.participants = event.participants.filter(
											(p) => !selections.has(p.email),
										)
										unselectAll()
									}
								"
							/>
						</template>
					</ListSelectBanner>
				</ListView>
				<FormControl
					v-if="!selectedEvent?.calendarEvent"
					v-model="event.send_scheduling_messages"
					:label="__('Send Invites and Updates')"
					type="checkbox"
				/>
			</div>
		</template>
	</Dialog>
	<EventRepeatSettingsModal
		v-model="showRepeatSettings"
		@update-recurrence-rule="(val) => (event.recurrence_rule = val)"
	/>
</template>
