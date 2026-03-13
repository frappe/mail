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

import { raiseToast } from '@/utils'

const show = defineModel<boolean>()

const { selectedEvent } = defineProps<{ selectedEvent: any }>()

const emit = defineEmits(['reload-events'])

const user = inject('$user')
const dayjs = inject('$dayjs')

const DEFAULT_EVENT = {
	title: '',
	isFullDay: true,
	startDate: dayjs().format('YYYY-MM-DD'),
	startTime: '10:00',
	endDate: dayjs().format('YYYY-MM-DD'),
	endTime: '10:30',
	location: '',
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
			locations: [{ _name: event.location }],
			participants: event.participants,
			description: event.description,
			send_scheduling_messages: event.send_scheduling_messages,
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
	title: __('Add Event'),
	size: '2xl',
	actions: [{ label: __('Save'), variant: 'solid', onClick: () => createEvent.submit() }],
}))

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
					autocomplete="off"
				/>
				<FormControl v-model="event.isFullDay" :label="__('All Day')" type="checkbox" />
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
					v-model="event.location"
					:label="__('Location')"
					:placeholder="__('Meeting location')"
					autocomplete="off"
				/>
				<FormControl
					v-model="event.description"
					:label="__('Description')"
					type="textarea"
					:placeholder="__('Event description')"
					autocomplete="off"
				/>

				<hr />

				<h3 class="text-base font-medium">{{ __('Enter Participants') }}</h3>

				<Combobox
					v-model="participantsInput"
					:options="mailContacts?.data || []"
					placeholder="john@example.com"
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
					v-model="event.send_scheduling_messages"
					:label="__('Send Invites and Updates')"
					type="checkbox"
				/>
			</div>
		</template>
	</Dialog>
</template>
