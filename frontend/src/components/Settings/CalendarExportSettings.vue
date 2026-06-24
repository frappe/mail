<template>
	<FormControl
		v-model="calendarExport.format"
		:label="__('Format')"
		type="select"
		variant="outline"
		:options="FORMAT_OPTIONS"
	/>
	<FormControl
		v-model="calendarExport.archive_type"
		:label="__('Archive Type')"
		type="select"
		variant="outline"
		:options="ARCHIVE_TYPE_OPTIONS"
	/>
	<Switch
		v-model="customSelection"
		:label="__('Custom Selection')"
		:description="__('Apply filters to select specific events for export.')"
		class="hover:!bg-surface-white !cursor-default !p-0"
	/>
	<template v-if="customSelection">
		<FormControl
			v-model="filter.inCalendar"
			:label="__('Calendar')"
			type="select"
			variant="outline"
			:options="calendarOptions"
		/>
		<FormControl v-model="filter.title" type="text" variant="outline" :label="__('Title')" />
		<FormControl
			v-model="filter.after"
			type="date"
			variant="outline"
			:label="__('From Date')"
		/>
		<FormControl
			v-model="filter.before"
			type="date"
			variant="outline"
			:label="__('To Date')"
		/>
		<FormControl
			v-model="calendarExport.limit"
			:label="__('Max Number of Events')"
			type="number"
			variant="outline"
			placeholder="1000"
		/>
		<FormControl
			v-if="calendarExport.limit && calendarExport.limit > 0"
			v-model="calendarExport.sort"
			:label="__('Start From')"
			type="select"
			variant="outline"
			:options="sortOptions"
		/>
	</template>

	<Button
		class="min-h-7"
		:label="__('Create Export')"
		:loading="ongoingExport.data?.name"
		:disabled="ongoingExport.loading || ongoingExport.error || createCalendarExport.loading"
		@click="createCalendarExport.submit()"
	/>
	<div class="!mt-3 space-x-1 text-base">
		<span class="text-ink-gray-5">{{ exportSubtitle }}</span>
		<a class="hover:underline" :href="exportHref" target="_blank">
			{{ exportLinkText }}
		</a>
	</div>
	<ErrorMessage
		v-if="createCalendarExport.error"
		:message="createCalendarExport.error"
		class="mb-2.5"
	/>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, reactive, ref } from 'vue'
import { Button, ErrorMessage, FormControl, Switch, createResource } from 'frappe-ui'

import { userStore } from '@/stores/user'

const { accountId, user: sessionUser } = userStore()

const user = inject('$user')
const socket = inject('$socket')

const calendarExport = reactive({
	format: 'jmap',
	archive_type: '.zip',
	sort: 'Start (ASC)',
	limit: undefined,
})

const customSelection = ref(false)

const filter = reactive({
	inCalendar: '',
	title: '',
	after: '',
	before: '',
})

const calendars = createResource({
	url: 'mail.client.doctype.calendar.calendar.fetch_calendars',
	auto: true,
	makeParams: () => ({ account: `${sessionUser}:${accountId}`, limit: 100 }),
})

const calendarOptions = computed(() =>
	[{ label: __(''), value: ' ' }].concat(
		(calendars.data || []).map((c: { id: string; _name: string }) => ({
			label: c._name,
			value: c.id,
		})),
	),
)

const sortOptions = computed(() => [
	{ label: __('Oldest Events'), value: 'Start (ASC)' },
	{ label: __('Newest Events'), value: 'Start (DESC)' },
])

const createCalendarExport = createResource({
	url: 'mail.api.account.create_calendar_export',
	makeParams: () => {
		const cleanedFilter = Object.fromEntries(
			Object.entries(filter)
				.map(([k, v]) => [k, typeof v === 'string' ? v.trim() : v])
				.filter(([, v]) => Boolean(v)),
		)
		return { account_id: accountId, ...calendarExport, filter: cleanedFilter }
	},
	onSuccess: () => ongoingExport.reload(),
})

const ongoingExport = createResource({
	url: 'frappe.client.get_value',
	auto: true,
	makeParams: () => ({
		doctype: 'Calendar Exchange',
		fieldname: 'name',
		filters: {
			user: user.data.name,
			operation: 'Export',
			status: ['in', ['Queued', 'In Progress']],
		},
	}),
})

onMounted(() =>
	socket.on('calendar_exchange_completed', (payload: { action: 'Import' | 'Export' }) => {
		if (payload.action === 'Export') ongoingExport.reload()
	}),
)

const exportSubtitle = computed(() => {
	if (ongoingExport.data?.name) return __("Export in progress. We'll email you when it's ready.")
	return __('No exports in progress.')
})

const exportHref = computed(() => {
	if (ongoingExport.data?.name) return `/mail/calendar-exchanges/${ongoingExport.data.name}`
	return '/mail/calendar-exchanges?operation=Export'
})

const exportLinkText = computed(() => {
	if (ongoingExport.data?.name) return __('Track status')
	return __('View history')
})

const FORMAT_OPTIONS = ['jmap', 'ics']
const ARCHIVE_TYPE_OPTIONS = ['.zip', '.tgz', '.tar.gz']
</script>
