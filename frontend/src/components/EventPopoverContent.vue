<script setup lang="ts">
import { computed, inject } from 'vue'
import { Button, Dropdown, FeatherIcon, createResource, toast } from 'frappe-ui'

import { raiseToast } from '@/utils'

const { calendarEvent, close } = defineProps<{ calendarEvent: any; close: () => void }>()

const emit = defineEmits(['edit', 'reloadEvents'])

const user = inject('$user')

const edit = () => {
	emit('edit')
	close()
}

const deleteOptions = computed(() => [
	{
		label: __('This instance'),
		onClick: () =>
			toast.promise(deleteEventInstance.submit(), {
				loading: __('Deleting event...'),
				success: __('Event deleted.'),
			}),
	},
	{
		label: __('This and following instances'),
		onClick: () =>
			toast.promise(deleteEvent.submit(calendarEvent.date), {
				loading: __('Deleting events...'),
				success: __('Events deleted.'),
			}),
	},
	{
		label: __('Entire series'),
		onClick: () =>
			toast.promise(deleteEvent.submit(), {
				loading: __('Deleting events...'),
				success: __('Events deleted.'),
			}),
	},
])

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
	<div class="bg-surface-modal text-ink-gray-8 w-96 rounded p-4 shadow-xl" @click.stop>
		<div class="flex justify-end space-x-2">
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
				@click="deleteEvent.submit"
			/>
			<Button :tooltip="__('Close')" variant="ghost" icon="x" @click="close" />
		</div>
		<div class="flex flex-col gap-5">
			<div class="flex justify-between text-xl font-semibold">
				<span>{{ calendarEvent.title || 'New Event' }}</span>
			</div>
			<div class="flex flex-col gap-4">
				<div class="flex items-center gap-2">
					<FeatherIcon name="calendar" class="h-4 w-4" />
					<span class="text-sm font-normal"> hi </span>
				</div>
				<div v-if="calendarEvent.participant" class="flex items-center gap-2">
					<FeatherIcon name="user" class="h-4 w-4" />
					<span class="text-sm font-normal">
						{{ calendarEvent.participant }}
					</span>
				</div>
				<div
					v-if="calendarEvent.fromTime && calendarEvent.toTime"
					class="flex items-center gap-2"
				>
					<FeatherIcon name="clock" class="h-4 w-4" />
					<span class="text-sm font-normal">
						{{ calendarEvent.fromTime }} - {{ calendarEvent.toTime }}
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
	</div>
</template>
