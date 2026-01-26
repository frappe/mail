<template>
	<div :class="{ 'fixed left-0 right-0 z-20': isMobile }" :style="{ bottom: toolbarBottom }">
		<div
			class="flex flex-wrap justify-between gap-2 overflow-hidden pt-2.5"
			:class="{ 'pb-2.5': isMobile }"
		>
			<!-- Text editor buttons -->
			<div class="flex items-center gap-1 overflow-x-auto" :class="{ 'px-3': isMobile }">
				<TextEditorFixedMenu :buttons class="!bg-inherit" />
				<EmojiPicker
					v-if="!isMobile"
					v-slot="{ togglePopover }"
					@update:model-value="emit('appendEmoji', $event)"
				>
					<Button variant="ghost" class="max-h-6 max-w-6" @click="togglePopover()">
						<template #icon>
							<Laugh class="h-4 w-4" />
						</template>
					</Button>
				</EmojiPicker>
				<Button variant="ghost" class="max-h-6 max-w-6" @click="fileInput?.click()">
					<template #icon>
						<Paperclip class="h-4 w-4" />
					</template>
				</Button>
				<input
					ref="fileInput"
					type="file"
					class="hidden"
					multiple
					@change="onFilesSelected"
				/>
			</div>

			<!-- Send & Discard -->
			<div v-if="!isMobile" class="ml-auto flex items-center space-x-2">
				<span v-if="isSavingDraft" class="text-ink-gray-5 text-base italic">
					{{ __('Saving Draft...') }}
				</span>
				<Button
					:label="__('Discard')"
					:tooltip="__('Discard ({0}+D)', [modifier])"
					:icon-left="Trash2"
					@click="emit('discardMail')"
				/>
				<Popover placement="top-end" @open="initScheduleDateTime">
					<template #target="{ togglePopover, isOpen }">
						<Button
							:label="__('Schedule')"
							:tooltip="__('Schedule send')"
							:icon-left="CalendarClock"
							:class="{ 'ring-2 ring-blue-300': isOpen }"
							@click="togglePopover()"
						/>
					</template>
					<template #body="{ close }">
						<div
							class="bg-surface-white border-outline-gray-1 mb-2 rounded-lg border p-4 shadow-xl"
						>
							<!-- Header -->
							<div class="text-ink-gray-7 mb-3 text-sm font-medium">
								{{ __('Schedule Send') }}
							</div>

							<!-- Inline Calendar UI -->
							<div class="border-outline-gray-2 mb-3 rounded-lg border p-2">
								<!-- Month/Year Header -->
								<div class="mb-2 flex items-center justify-between">
									<span class="text-ink-gray-8 text-base font-semibold">
										{{ monthNames[currentMonth] }} {{ currentYear }}
									</span>
									<div class="flex items-center gap-1">
										<Button
											variant="ghost"
											size="sm"
											class="!p-1"
											@click="prevMonth"
										>
											<template #icon>
												<ChevronLeft class="h-4 w-4" />
											</template>
										</Button>
										<div class="flex gap-0.5">
											<span
												class="bg-ink-gray-4 h-1.5 w-1.5 rounded-full"
											></span>
											<span
												class="bg-ink-gray-4 h-1.5 w-1.5 rounded-full"
											></span>
										</div>
										<Button
											variant="ghost"
											size="sm"
											class="!p-1"
											@click="nextMonth"
										>
											<template #icon>
												<ChevronRight class="h-4 w-4" />
											</template>
										</Button>
									</div>
								</div>

								<!-- Day Names -->
								<div
									class="border-outline-gray-2 mb-1 grid grid-cols-7 border-b pb-1"
								>
									<div
										v-for="day in ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']"
										:key="day"
										class="text-ink-gray-5 py-1 text-center text-xs font-medium"
									>
										{{ day }}
									</div>
								</div>

								<!-- Calendar Grid -->
								<div class="grid grid-cols-7 gap-y-0.5">
									<button
										v-for="dateObj in calendarDates"
										:key="dateObj.key"
										type="button"
										class="flex h-7 w-full items-center justify-center rounded text-sm transition-colors"
										:class="[
											dateObj.inMonth
												? 'text-ink-gray-7'
												: 'text-ink-gray-3',
											dateObj.isToday && !dateObj.isSelected
												? 'bg-blue-50 font-bold text-blue-600'
												: '',
											dateObj.isSelected
												? 'bg-blue-100 font-semibold text-blue-700'
												: 'hover:bg-surface-gray-2',
											dateObj.isPast && !dateObj.isToday
												? 'text-ink-gray-3 cursor-not-allowed'
												: 'cursor-pointer',
										]"
										:disabled="dateObj.isPast && !dateObj.isToday"
										@click="selectDate(dateObj)"
									>
										{{ dateObj.day }}
									</button>
								</div>
							</div>

							<!-- Time Picker and Buttons -->
							<div class="flex items-center justify-between gap-4">
								<TimePicker
									v-model="scheduledTime"
									:use12-hour="true"
									:interval="15"
									placeholder="Select time"
									class="w-32"
								/>
								<div class="flex gap-2">
									<Button :label="__('Cancel')" @click="close()" />
									<Button
										variant="solid"
										:label="__('Schedule')"
										:disabled="!isValidScheduleTime"
										@click="onScheduleSend(close)"
									/>
								</div>
							</div>
						</div>
					</template>
				</Popover>
				<Button
					variant="solid"
					:label="__('Send')"
					:tooltip="__('Send ({0}+Enter)', [modifier])"
					:icon-left="SendHorizontal"
					:disabled="isRecipientsEmpty"
					@click="emit('sendMail')"
				/>
			</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import { computed, ref, useTemplateRef } from 'vue'
import {
	CalendarClock,
	ChevronLeft,
	ChevronRight,
	Laugh,
	Paperclip,
	SendHorizontal,
	Trash2,
} from 'lucide-vue-next'
import { Button, Popover, TextEditorFixedMenu, TimePicker } from 'frappe-ui'

import { isMac } from '@/utils'
import { useScreenSize, useTextEditorButtons, useVisualViewport } from '@/utils/composables'
import EmojiPicker from '@/components/EmojiPicker.vue'

const { isSavingDraft, isRecipientsEmpty } = defineProps<{
	isSavingDraft: boolean
	isRecipientsEmpty: boolean
}>()

const emit = defineEmits(['appendEmoji', 'selectFiles', 'discardMail', 'sendMail', 'scheduleMail'])

const modifier = computed(() => (isMac ? '⌘' : 'Ctrl'))

// Schedule send state
const scheduledDate = ref('')
const scheduledTime = ref('')
const currentYear = ref(new Date().getFullYear())
const currentMonth = ref(new Date().getMonth())

const monthNames = [
	'Jan',
	'Feb',
	'Mar',
	'Apr',
	'May',
	'Jun',
	'Jul',
	'Aug',
	'Sep',
	'Oct',
	'Nov',
	'Dec',
]

// Calendar logic
interface DateObj {
	key: string
	day: number
	date: Date
	inMonth: boolean
	isToday: boolean
	isSelected: boolean
	isPast: boolean
}

const calendarDates = computed((): DateObj[] => {
	const dates: DateObj[] = []
	const year = currentYear.value
	const month = currentMonth.value

	// First day of month (0 = Sunday, we want Monday = 0)
	const firstDay = new Date(year, month, 1)
	let startDay = firstDay.getDay() - 1
	if (startDay < 0) startDay = 6 // Sunday becomes 6

	// Last day of month
	const lastDay = new Date(year, month + 1, 0).getDate()

	// Previous month days
	const prevMonthLastDay = new Date(year, month, 0).getDate()
	for (let i = startDay - 1; i >= 0; i--) {
		const day = prevMonthLastDay - i
		const date = new Date(year, month - 1, day)
		dates.push(createDateObj(date, day, false))
	}

	// Current month days
	for (let day = 1; day <= lastDay; day++) {
		const date = new Date(year, month, day)
		dates.push(createDateObj(date, day, true))
	}

	// Next month days (fill to 42 cells = 6 weeks)
	const remaining = 42 - dates.length
	for (let day = 1; day <= remaining; day++) {
		const date = new Date(year, month + 1, day)
		dates.push(createDateObj(date, day, false))
	}

	return dates
})

const createDateObj = (date: Date, day: number, inMonth: boolean): DateObj => {
	const today = new Date()
	today.setHours(0, 0, 0, 0)
	const dateOnly = new Date(date)
	dateOnly.setHours(0, 0, 0, 0)

	const selectedDateObj = scheduledDate.value ? new Date(scheduledDate.value) : null
	if (selectedDateObj) selectedDateObj.setHours(0, 0, 0, 0)

	return {
		key: date.toISOString(),
		day,
		date,
		inMonth,
		isToday: dateOnly.getTime() === today.getTime(),
		isSelected: selectedDateObj ? dateOnly.getTime() === selectedDateObj.getTime() : false,
		isPast: dateOnly < today,
	}
}

const prevMonth = () => {
	if (currentMonth.value === 0) {
		currentMonth.value = 11
		currentYear.value--
	} else {
		currentMonth.value--
	}
}

const nextMonth = () => {
	if (currentMonth.value === 11) {
		currentMonth.value = 0
		currentYear.value++
	} else {
		currentMonth.value++
	}
}

const selectDate = (dateObj: DateObj) => {
	if (dateObj.isPast && !dateObj.isToday) return

	// Format as YYYY-MM-DD
	const year = dateObj.date.getFullYear()
	const month = String(dateObj.date.getMonth() + 1).padStart(2, '0')
	const day = String(dateObj.date.getDate()).padStart(2, '0')
	scheduledDate.value = `${year}-${month}-${day}`

	// Navigate to the selected month if in different month
	if (!dateObj.inMonth) {
		currentYear.value = dateObj.date.getFullYear()
		currentMonth.value = dateObj.date.getMonth()
	}
}

// Initialize with default time (1 hour from now, rounded to next 30 min)
const initScheduleDateTime = () => {
	const now = new Date()
	now.setHours(now.getHours() + 1)
	// Round to next 30 minutes
	const minutes = now.getMinutes()
	now.setMinutes(minutes < 30 ? 30 : 60)
	now.setSeconds(0)
	now.setMilliseconds(0)

	// Set date
	currentYear.value = now.getFullYear()
	currentMonth.value = now.getMonth()

	const year = now.getFullYear()
	const month = String(now.getMonth() + 1).padStart(2, '0')
	const day = String(now.getDate()).padStart(2, '0')
	scheduledDate.value = `${year}-${month}-${day}`

	// Set time in HH:mm format
	const hours = String(now.getHours()).padStart(2, '0')
	const mins = String(now.getMinutes()).padStart(2, '0')
	scheduledTime.value = `${hours}:${mins}`
}

// Validate that scheduled time is in the future
const isValidScheduleTime = computed(() => {
	if (!scheduledDate.value || !scheduledTime.value || isRecipientsEmpty) return false

	const [hours, minutes] = scheduledTime.value.split(':').map(Number)
	const scheduled = new Date(scheduledDate.value)
	scheduled.setHours(hours, minutes, 0, 0)

	return scheduled > new Date()
})

const onScheduleSend = (close: () => void) => {
	if (scheduledDate.value && scheduledTime.value && isValidScheduleTime.value) {
		const [hours, minutes] = scheduledTime.value.split(':').map(Number)
		const scheduled = new Date(scheduledDate.value)
		scheduled.setHours(hours, minutes, 0, 0)

		// Format as local datetime string (YYYY-MM-DD HH:MM:SS) instead of UTC ISO string
		const year = scheduled.getFullYear()
		const month = String(scheduled.getMonth() + 1).padStart(2, '0')
		const day = String(scheduled.getDate()).padStart(2, '0')
		const hrs = String(scheduled.getHours()).padStart(2, '0')
		const mins = String(scheduled.getMinutes()).padStart(2, '0')
		const scheduledAtLocal = `${year}-${month}-${day} ${hrs}:${mins}:00`

		emit('scheduleMail', scheduledAtLocal)
		scheduledDate.value = ''
		scheduledTime.value = ''
		close()
	}
}

// Make toolbar hover over keyboard on mobile
const { isMobile } = useScreenSize()
const { buttons } = useTextEditorButtons()

const toolbarBottom = useVisualViewport(
	(viewport) => `${window.innerHeight - viewport.height - viewport.offsetTop}px`,
)

const fileInput = useTemplateRef('fileInput')

const onFilesSelected = async (e: Event) => {
	const input = e.target as HTMLInputElement
	const files = Array.from(input.files ?? [])
	if (!files.length) return

	emit('selectFiles', files)
	input.value = ''
}
</script>
