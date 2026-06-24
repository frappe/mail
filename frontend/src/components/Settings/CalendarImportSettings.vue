<template>
	<h1>{{ __('Import Calendar') }}</h1>
	<FormControl
		v-model="calendarImport.format"
		:label="__('Format')"
		type="select"
		variant="outline"
		:options="FORMAT_OPTIONS"
		required
	/>
	<FormControl
		v-model="calendarImport.calendar"
		:label="__('Calendar')"
		type="select"
		variant="outline"
		:options="calendarOptions"
	/>
	<input
		ref="fileInput"
		type="file"
		class="hidden"
		:accept="acceptTypes"
		@change="onFileSelected"
	/>
	<Button
		class="w-full"
		:label="uploading ? __('Uploading ({0}%)', [progress]) : __('Upload File')"
		:loading="uploading"
		@click="fileInput?.click()"
	/>
	<p class="text-ink-gray-5 mt-2 flex text-sm">{{ fileUploadSubtitle }}</p>

	<Button
		class="min-h-7"
		:label="__('Create Import')"
		variant="solid"
		:loading="ongoingImport.data?.name"
		:disabled="ongoingImport.loading || ongoingImport.error || !calendarImport.file"
		@click="createCalendarImport.submit()"
	/>
	<div class="!mt-3 space-x-1 text-base">
		<span class="text-ink-gray-5">{{ importSubtitle }}</span>
		<a class="hover:underline" :href="importHref" target="_blank">
			{{ importLinkText }}
		</a>
	</div>
	<ErrorMessage
		v-if="createCalendarImport.error"
		:message="createCalendarImport.error"
		class="mb-2.5"
	/>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, reactive, ref } from 'vue'
import { Button, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { useChunkedUpload } from '@/utils/useChunkedUpload'
import { userStore } from '@/stores/user'

const { accountId, user: sessionUser } = userStore()

const user = inject('$user')
const socket = inject('$socket')

const calendarImport = reactive({
	format: 'ics',
	file: '',
	calendar: '',
})

const fileInput = ref<HTMLInputElement | null>(null)
const { uploading, progress, upload } = useChunkedUpload()

const acceptTypes = computed(() =>
	calendarImport.format === 'ics' ? '.ics' : '.zip,.tgz,.tar.gz',
)

// Upload in chunks so large import archives aren't blocked by the web server's request-size limit.
const onFileSelected = async (event: Event) => {
	const input = event.target as HTMLInputElement
	const file = input.files?.[0]
	input.value = '' // let the same file be re-selected after an error
	if (!file) return

	try {
		const uploaded = await upload(file, { private: true })
		calendarImport.file = uploaded.file_url
	} catch (error) {
		raiseToast((error as Error).message, 'error')
	}
}

const calendars = createResource({
	url: 'mail.client.doctype.calendar.calendar.fetch_calendars',
	auto: true,
	makeParams: () => ({ account: `${sessionUser}:${accountId}`, limit: 100 }),
})

const calendarOptions = computed(() =>
	[{ label: __('Default'), value: '' }].concat(
		(calendars.data || []).map((c: { id: string; _name: string }) => ({
			label: c._name,
			value: c.id,
		})),
	),
)

const fileUploadSubtitle = computed(() => {
	if (calendarImport.file) return __('File uploaded: {0}', [calendarImport.file])
	if (calendarImport.format === 'ics') return __('Supported file format: .ics')
	return __('Supported file formats: .zip, .tar, .tgz')
})

const createCalendarImport = createResource({
	url: 'mail.api.account.create_calendar_import',
	makeParams: () => ({ account_id: accountId, ...calendarImport }),
	onSuccess: () => ongoingImport.reload(),
})

const ongoingImport = createResource({
	url: 'frappe.client.get_value',
	auto: true,
	makeParams: () => ({
		doctype: 'Calendar Exchange',
		fieldname: 'name',
		filters: {
			user: user.data.name,
			operation: 'Import',
			status: ['in', ['Queued', 'In Progress']],
		},
	}),
})

onMounted(() =>
	socket.on('calendar_exchange_completed', (payload: { action: 'Import' | 'Export' }) => {
		if (payload.action === 'Import') ongoingImport.reload()
	}),
)

const importSubtitle = computed(() => {
	if (ongoingImport.data?.name) return __("Import in progress. We'll email you when it's ready.")
	return __('No imports in progress.')
})

const importHref = computed(() => {
	if (ongoingImport.data?.name) return `/mail/calendar-exchanges/${ongoingImport.data.name}`
	return '/mail/calendar-exchanges?operation=Import'
})

const importLinkText = computed(() => {
	if (ongoingImport.data?.name) return __('Track status')
	return __('View history')
})

const FORMAT_OPTIONS = ['ics', 'jmap']
</script>
