<script setup lang="ts">
import { computed, inject, reactive, ref, watch } from 'vue'
import {
	Button,
	Dialog,
	FormControl,
	ListHeader,
	ListRows,
	ListSelectBanner,
	ListView,
	createResource,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import ContactsModal from '@/components/Modals/ContactsModal.vue'

const show = defineModel<boolean>()

const { selectedEvent } = defineProps<{ selectedEvent: any }>()

const emit = defineEmits(['reload-events'])

const user = inject('$user')
const dayjs = inject('$dayjs')

const step = ref(0)
const participantInput = ref('')
const showContactsModal = ref(false)

const DEFAULT_EVENT = {
	title: '',
	isFullDay: true,
	startDate: dayjs().format('YYYY-MM-DD'),
	startTime: '10:00',
	endDate: dayjs().format('YYYY-MM-DD'),
	endTime: '10:30',
	description: '',
	participants: [] as Array<{ email: string }>,
	send_scheduling_messages: false,
}

const event = reactive({ ...DEFAULT_EVENT })

watch(show, (val) => {
	if (!val) return
	Object.assign(event, DEFAULT_EVENT)
	if (dayjs(selectedEvent.date).format('YYYY-MM-DD') === event.startDate) {
		event.startTime = dayjs().add(1, 'hour').minute(0).second(0).format('HH:mm')
		event.endTime = dayjs(event.startTime, 'HH:mm').add(30, 'minute').format('HH:mm')
	} else {
		event.startDate = dayjs(selectedEvent.date).format('YYYY-MM-DD')
		event.endDate = dayjs(selectedEvent.date).format('YYYY-MM-DD')
	}
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

const handleParticipantEnter = () => {
	const value = participantInput.value.trim()
	if (!value) return
	const emails = value
		.split(',')
		.map((e) => e.trim())
		.filter((e) => e)
	emails.forEach(addParticipant)
	participantInput.value = ''
}

const createEvent = createResource({
	url: 'mail.client.doctype.calendar_event.calendar_event.add_calendar_event',
	makeParams: () => {
		const start = dayjs(event.startDate + 'T' + event.startTime)
		let duration: string
		if (event.isFullDay) {
			const startDay = dayjs(event.startDate)
			const endDay = dayjs(event.endDate)
			const days = endDay.diff(startDay, 'day') + 1
			duration = 'P' + days + 'D'
		} else {
			duration = 'PT'
			const end = dayjs(event.endDate + 'T' + event.endTime)
			const totalMinutes = end.diff(start, 'minute')
			const hours = Math.floor(totalMinutes / 60)
			const minutes = totalMinutes % 60
			if (hours > 0) duration += hours + 'H'
			if (minutes > 0) duration += minutes + 'M'
			if (hours === 0 && minutes === 0) duration += '0M'
		}

		return {
			user: user.data.name,
			organizer: user.data.name,
			title: event.title,
			start: start.format('YYYY-MM-DD[T]HH:mm:ss'),
			duration,
			participants: event.participants,
			description: event.description,
			send_scheduling_messages: event.send_scheduling_messages,
		}
	},
	onSuccess: () => {
		raiseToast(__('Event created successfully'), 'success')
		show.value = false
		emit('reload-events')
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

const dialogOptions = computed(() => {
	const actions = []
	if (step.value === 1) actions.push({ label: __('Previous'), onClick: () => step.value-- })
	actions.push({
		label: step.value ? __('Save') : __('Next'),
		variant: 'solid',
		onClick: () => (step.value ? createEvent.submit() : step.value++),
	})

	return { title: __('Add Event'), size: 'xl', actions }
})

const PARTICIPANT_COLUMNS = [{ label: __('Email'), key: 'email' }]
</script>

<template>
	<Dialog v-model="show" :options="dialogOptions">
		<template #body-content>
			<div class="space-y-4">
				<template v-if="step === 0">
					<FormControl
						v-model="event.title"
						:label="__('Title')"
						placeholder="example.com"
						autocomplete="off"
					/>
					<FormControl
						v-model="event.isFullDay"
						:label="__('All Day')"
						type="checkbox"
					/>
					<div class="flex space-x-4">
						<FormControl
							v-model="event.startDate"
							type="date"
							:label="__('Start Date')"
							autocomplete="off"
							class="w-full"
						/>
						<FormControl
							v-if="!event.isFullDay"
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
							autocomplete="off"
							class="w-full"
						/>
						<FormControl
							v-if="!event.isFullDay"
							v-model="event.endTime"
							type="time"
							:label="__('End Time')"
							class="w-full"
						/>
					</div>
					<FormControl
						v-model="event.description"
						:label="__('Description')"
						type="textarea"
						placeholder="example.com"
						autocomplete="off"
					/>
				</template>
				<template v-else>
					<FormControl
						v-model="participantInput"
						:label="__('Enter Participants')"
						placeholder="name@example.com"
						autocomplete="email"
						@keyup.enter="handleParticipantEnter"
					/>
					<button class="!mt-2 text-sm text-blue-500" @click="showContactsModal = true">
						{{ __('Choose from contacts') }}
					</button>
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
						v-model="event.send_scheduling_messages"
						:label="__('Send Invites and Updates')"
						type="checkbox"
					/>
				</template>
			</div>
		</template>
	</Dialog>
	<ContactsModal
		v-model="showContactsModal"
		@insert="(emails) => emails.forEach(addParticipant)"
	/>
</template>
