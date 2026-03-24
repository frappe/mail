<script setup lang="ts">
import { computed, inject } from 'vue'
import { CalendarDays } from 'lucide-vue-next'
import { Button, Dropdown, FeatherIcon, createResource, toast } from 'frappe-ui'

import { raiseToast } from '@/utils'

const { calendarEvent, close } = defineProps<{ calendarEvent: any; close: () => void }>()

const emit = defineEmits(['edit', 'reloadEvents'])

const user = inject('$user')
const dayjs = inject('$dayjs')

const date = computed(() => {
	const start = dayjs(calendarEvent.start)
	const duration = dayjs.duration(calendarEvent.duration)
	const end = start.add(duration)
	const isFullDay = duration.asHours() % 24 === 0 && start.isSame(start.startOf('day'))
	const isSameDay =
		start.isSame(end, 'day') || (isFullDay && start.isSame(end.subtract(1, 'ms'), 'day'))

	if (isFullDay) {
		if (isSameDay) return start.format('ddd, MMM D')
		else return `${start.format('MMM D')} - ${end.subtract(1, 'day').format('MMM D')}`
	} else {
		if (isSameDay)
			return `${start.format('ddd, MMM D')} · ${start.format('HH:mm')} - ${end.format('HH:mm')}`
		else
			return `${start.format('MMM D')}, ${start.format('HH:mm')} - ${end.format('MMM D')}, ${end.format('HH:mm')}`
	}
})

const edit = () => {
	emit('edit')
	close()
}

const deleteOptions = computed(() => [
	{ label: __('This instance'), onClick: () => handleDeleteEventInstance() },
	{
		label: __('This and following instances'),
		onClick: () => handleDeleteEvent(calendarEvent.date),
	},
	{ label: __('Entire series'), onClick: () => handleDeleteEvent() },
])

const handleDeleteEventInstance = () =>
	toast.promise(deleteEventInstance.submit(), {
		loading: __('Deleting event...'),
		success: __('Event deleted.'),
	})

const handleDeleteEvent = (date?: string) =>
	toast.promise(deleteEvent.submit(date), {
		loading: calendarEvent.recurrence_id ? __('Deleting events...') : __('Deleting event...'),
		success: calendarEvent.recurrence_id ? __('Events deleted.') : __('Event deleted.'),
	})

const deleteEvent = createResource({
	url: 'mail.api.calendar.delete_event',
	makeParams: (until?: string) => ({
		uid: calendarEvent.uid,
		until: until ? `${until}T00:00:00Z` : undefined,
	}),
	onSuccess: () => {
		close()
		emit('reloadEvents')
	},
	onError: (error) => {
		raiseToast(error.message, 'error')
		emit('reloadEvents')
	},
})

const deleteEventInstance = createResource({
	url: 'mail.client.doctype.calendar_event.calendar_event.delete_calendar_event_instance',
	makeParams: () => ({
		user: user.data.name,
		uid: calendarEvent.uid,
		recurrence_id: calendarEvent.recurrence_id,
	}),
	onSuccess: () => {
		close()
		emit('reloadEvents')
	},
	onError: (error) => {
		raiseToast(error.message, 'error')
		emit('reloadEvents')
	},
})
</script>

<template>
	<div class="bg-surface-modal text-ink-gray-8 w-[32rem] rounded p-5 shadow-xl" @click.stop>
		<div class="mb-2 flex justify-end space-x-2">
			<Button :tooltip="__('Edit')" variant="ghost" icon="edit-2" @click="edit" />
			<Dropdown v-if="calendarEvent.recurrence_id" :options="deleteOptions">
				<Button
					:tooltip="__('Delete')"
					:loading="deleteEvent.loading || deleteEventInstance.loading"
					variant="ghost"
					icon="trash-2"
				/>
			</Dropdown>
			<Button
				v-else
				:tooltip="__('Delete')"
				:loading="deleteEvent.loading"
				variant="ghost"
				icon="trash-2"
				@click="handleDeleteEvent"
			/>
			<Button :tooltip="__('Close')" variant="ghost" icon="x" @click="close" />
		</div>
		<div class="flex flex-col gap-4">
			<h2
				class="flex items-center space-x-2 text-left"
				:class="{ italic: !calendarEvent.title }"
			>
				<span class="h-4 w-4 shrink-0 rounded-full bg-blue-500" />
				<span class="truncate">
					{{ calendarEvent.title || __('[No title]') }}
				</span>
			</h2>
			<div class="flex items-center gap-2">
				<CalendarDays class="stroke-1.5 text-ink-gray-5 h-4 w-4" />
				<span class="text-sm"> {{ date }} </span>
			</div>
			<div v-if="calendarEvent.participant" class="flex items-center gap-2">
				<FeatherIcon name="user" class="h-4 w-4" />
				<span class="text-sm font-normal">
					{{ calendarEvent.participant }}
				</span>
			</div>
			<div v-if="calendarEvent.venue" class="flex items-center gap-2">
				<FeatherIcon name="map-pin" class="h-4 w-4" />
				<span class="text-sm font-normal">
					{{ calendarEvent.venue }}
				</span>
			</div>
		</div>
	</div>
</template>
