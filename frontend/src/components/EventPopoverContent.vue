<script setup lang="ts">
import { computed, inject, onMounted, ref, useTemplateRef } from 'vue'
import { CalendarDays, Edit2, Globe, MapPin, Repeat, Text, Trash2, Users } from 'lucide-vue-next'
import { Button, Dropdown, createResource, toast } from 'frappe-ui'

import { isUrl, raiseToast } from '@/utils'
import { getRepeatMessage } from '@/utils/format'

const { calendarEvent, close } = defineProps<{ calendarEvent: any; close: () => void }>()

const emit = defineEmits(['edit', 'reloadEvents'])

const user = inject('$user')
const dayjs = inject('$dayjs')

const descriptionExpanded = ref(false)
const descriptionRef = useTemplateRef('descriptionRef')
const isDescriptionClamped = ref(false)

onMounted(() => {
	const el = descriptionRef.value
	if (el) {
		isDescriptionClamped.value = el.scrollHeight > el.clientHeight
	}
})

const date = computed(() => {
	const start = dayjs(calendarEvent.start)
	const duration = dayjs.duration(calendarEvent.duration)
	const end = start.add(duration)
	const isFullDay = duration.asHours() % 24 === 0 && start.isSame(start.startOf('day'))
	const isSameDay =
		start.isSame(end, 'day') || (isFullDay && start.isSame(end.subtract(1, 'ms'), 'day'))

	const currentYear = dayjs().year()
	const showYear = start.year() !== currentYear || end.year() !== currentYear

	if (isFullDay) {
		if (isSameDay) return start.format(showYear ? 'ddd, MMM D, YYYY' : 'ddd, MMM D')
		else
			return `${start.format(showYear ? 'MMM D, YYYY' : 'MMM D')} - ${end.subtract(1, 'day').format(showYear ? 'MMM D, YYYY' : 'MMM D')}`
	} else {
		if (isSameDay)
			return `${start.format(showYear ? 'ddd, MMM D, YYYY' : 'ddd, MMM D')} · ${start.format('HH:mm')} - ${end.format('HH:mm')}`
		else
			return `${start.format(showYear ? 'MMM D, YYYY' : 'MMM D')}, ${start.format('HH:mm')} - ${end.format(showYear ? 'MMM D, YYYY' : 'MMM D')}, ${end.format('HH:mm')}`
	}
})

const participants = computed(() => {
	const total = calendarEvent.participants.length
	const accepted = calendarEvent.participants.filter(
		(p) => p.participation_status === 'ACCEPTED',
	)
	const declined = calendarEvent.participants.filter(
		(p) => p.participation_status === 'DECLINED',
	)
	const tentative = calendarEvent.participants.filter(
		(p) => p.participation_status === 'TENTATIVE',
	)
	const needsAction = calendarEvent.participants.filter(
		(p) => p.participation_status === 'NEEDS-ACTION',
	)

	const parts = [
		accepted.length && `${accepted.length} ${__('yes')}`,
		declined.length && `${declined.length} ${__('no')}`,
		tentative.length && `${tentative.length} ${__('maybe')}`,
		needsAction.length && `${needsAction.length} ${__('pending')}`,
	].filter(Boolean)

	return __('{0} {1} {2}', [
		total,
		total === 1 ? __('participant') : __('participants'),
		parts.length ? `(${parts.join(', ')})` : '',
	])
})

const edit = () => {
	emit('edit')
	close()
}

const options = computed(() => {
	const opts = [{ label: __('Edit'), icon: Edit2, onClick: edit }]

	if (calendarEvent.recurrence_id)
		opts.push({
			label: __('Delete'),
			icon: Trash2,
			submenu: [
				{ label: __('This instance'), onClick: () => handleDeleteEventInstance() },
				{
					label: __('This and following instances'),
					onClick: () => handleDeleteEvent(calendarEvent.date),
				},
				{ label: __('Entire series'), onClick: () => handleDeleteEvent() },
			],
		})
	else opts.push({ label: __('Delete'), icon: Trash2, onClick: () => handleDeleteEvent() })

	return opts
})

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

const openUrl = () => {
	const location = calendarEvent.locations[0]._name
	if (isUrl(location)) window.open(location, '_blank')
}
</script>

<template>
	<div class="bg-surface-modal text-ink-gray-8 w-[32rem] rounded shadow-xl" @click.stop>
		<div class="flex justify-between border-b p-5">
			<div class="space-y-2">
				<h2 class="flex gap-3 text-left" :class="{ italic: !calendarEvent.title }">
					{{ calendarEvent.title || __('[No title]') }}
				</h2>
				<div class="mt-px min-w-0 break-words text-left text-sm">{{ date }}</div>
			</div>
			<Dropdown
				:options
				:button="{
					icon: 'more-vertical',
					tooltip: __('Actions'),
					disabled: deleteEvent.loading || deleteEventInstance.loading,
					variant: 'ghost',
				}"
			/>
		</div>
		<div class="flex flex-col gap-4 p-5">
			<div v-if="calendarEvent.recurrence_id" class="flex gap-3">
				<Repeat class="stroke-1.5 text-ink-gray-5 h-4 w-4 shrink-0" />
				<span class="min-w-0 break-words text-left text-sm">
					{{ getRepeatMessage(JSON.parse(calendarEvent.recurrence_rule)) }}
				</span>
			</div>
			<div v-if="calendarEvent.locations.length" class="flex gap-3">
				<component
					:is="isUrl(calendarEvent.locations[0]._name) ? Globe : MapPin"
					class="stroke-1.5 text-ink-gray-5 h-4 w-4 shrink-0"
				/>
				<span
					class="mt-px min-w-0 break-words text-left text-sm"
					:class="{
						'text-ink-blue-3 cursor-pointer hover:underline': isUrl(
							calendarEvent.locations[0]._name,
						),
					}"
					@click="openUrl"
				>
					{{ calendarEvent.locations[0]._name }}
				</span>
			</div>
			<div class="flex gap-3">
				<Users class="stroke-1.5 text-ink-gray-5 h-4 w-4 shrink-0" />
				<span class="mt-px text-sm"> {{ participants }} </span>
			</div>
			<div v-if="calendarEvent.description" class="flex gap-3">
				<Text class="stroke-1.5 text-ink-gray-5 h-4 w-4 shrink-0" />
				<div class="mt-px min-w-0 text-left text-sm">
					<span
						ref="descriptionRef"
						class="break-words"
						:class="{ 'line-clamp-3': !descriptionExpanded }"
					>
						{{ calendarEvent.description }}
					</span>
					<button
						v-if="isDescriptionClamped && !descriptionExpanded"
						class="text-ink-blue-3 mt-0.5 block"
						@click="descriptionExpanded = true"
					>
						{{ __('Show more') }}
					</button>
				</div>
			</div>
			<div class="flex gap-3">
				<CalendarDays class="stroke-1.5 text-ink-gray-5 h-4 w-4 shrink-0" />
				<span class="mt-px min-w-0 break-words text-left text-sm">
					{{ calendarEvent.organizer }}
				</span>
			</div>
		</div>
		<div class="bg-surface-menu-bar flex items-center justify-between rounded-b border-t p-5">
			<div class="text-left text-sm">{{ __('Are you attending?') }}</div>
			<div class="flex gap-2">
				<Button :label="__('Yes')" variant="outline" />
				<Button :label="__('Maybe')" variant="outline" />
				<Button :label="__('No')" variant="outline" />
			</div>
		</div>
	</div>
</template>
