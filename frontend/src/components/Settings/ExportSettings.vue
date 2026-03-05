<template>
	<h1>{{ __('Export Mail') }}</h1>
	<FormControl
		v-model="mailExport.format"
		:label="__('Format')"
		type="select"
		variant="outline"
		:options="FORMAT_OPTIONS"
	/>
	<FormControl
		v-model="mailExport.archive_type"
		:label="__('Archive Type')"
		type="select"
		variant="outline"
		:options="ARCHIVE_TYPE_OPTIONS"
	/>
	<Switch
		v-model="customSelection"
		:label="__('Custom Selection')"
		:description="__('Apply filters to select specific emails for export')"
		class="hover:!bg-surface-white !cursor-default !p-0"
	/>
	<template v-if="customSelection">
		<FormControl
			v-model="filter.inMailbox"
			:label="__('Folder')"
			type="select"
			variant="outline"
			:options="mailboxOptions"
		/>
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
			v-model="filter.hasAttachment"
			type="select"
			variant="outline"
			:label="__('Attachments')"
			:options="getAttachmentOptions()"
		/>
		<FormControl
			v-model="filter.isRead"
			type="select"
			variant="outline"
			:label="__('Read Status')"
			:options="getReadStatusOptions()"
		/>
		<FormControl
			v-model="mailExport.limit"
			:label="__('Max Number of Emails')"
			type="number"
			variant="outline"
			placeholder="1000"
		/>
		<FormControl
			v-if="mailExport.limit && mailExport.limit > 0"
			v-model="mailExport.sort"
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
		:disabled="ongoingExport.loading || ongoingExport.error || createMailExport.loading"
		@click="createMailExport.submit()"
	/>
	<div class="!mt-3 space-x-1 text-base">
		<span class="text-ink-gray-5">{{ exportSubtitle }}</span>
		<a class="hover:underline" :href="exportHref" target="_blank">
			{{ exportLinkText }}
		</a>
	</div>
	<ErrorMessage v-if="createMailExport.error" :message="createMailExport.error" class="mb-2.5" />
</template>

<script setup lang="ts">
import { computed, inject, onMounted, reactive, ref } from 'vue'
import { Button, ErrorMessage, FormControl, Switch, createResource } from 'frappe-ui'

import { getAttachmentOptions, getReadStatusOptions } from '@/constants'
import { userStore } from '@/stores/user'

const { mailboxes } = userStore()

const user = inject('$user')
const socket = inject('$socket')

const mailExport = reactive({
	format: 'jmap',
	archive_type: '.zip',
	sort: 'Received At (ASC)',
	limit: undefined,
})

const customSelection = ref(false)

const filter = reactive({
	inMailbox: '',
	after: '',
	before: '',
	hasAttachment: ' ',
	isRead: ' ',
})

const mailboxOptions = computed(() =>
	[{ label: __(''), value: ' ' }].concat(
		mailboxes.data.map((m: { id: string; _name: string }) => ({
			label: m._name,
			value: m.id,
		})),
	),
)

const sortOptions = computed(() => [
	{ label: __('Oldest Emails'), value: 'Received At (ASC)' },
	{ label: __('Newest Emails'), value: 'Received At (DESC)' },
])

const createMailExport = createResource({
	url: 'mail.api.account.create_mail_export',
	makeParams: () => {
		const cleanedFilter = Object.fromEntries(
			Object.entries(filter)
				.map(([k, v]) => [k, typeof v === 'string' ? v.trim() : v])
				.filter(([, v]) => Boolean(v)),
		)
		return { ...mailExport, filter: cleanedFilter }
	},
	onSuccess: () => ongoingExport.reload(),
})

const ongoingExport = createResource({
	url: 'frappe.client.get_value',
	auto: true,
	makeParams: () => ({
		doctype: 'Mail Exchange',
		fieldname: 'name',
		filters: {
			user: user.data.name,
			operation: 'Export',
			status: ['in', ['Queued', 'In Progress']],
		},
	}),
})

onMounted(() =>
	socket.on('mail_exchange_completed', (payload: { action: 'Import' | 'Export' }) => {
		if (payload.action === 'Export') ongoingExport.reload()
	}),
)

const exportSubtitle = computed(() => {
	if (ongoingExport.data?.name) return __("Export in progress. We'll email you when it's ready.")
	return __('No exports in progress.')
})

const exportHref = computed(() => {
	if (ongoingExport.data?.name) return `/mail/mail-exchanges/${ongoingExport.data.name}`
	return '/mail/mail-exchanges?operation=Export'
})

const exportLinkText = computed(() => {
	if (ongoingExport.data?.name) return __('Track status')
	return __('View history')
})

const FORMAT_OPTIONS = ['jmap', 'mbox', 'maildir', 'maildir-nested']
const ARCHIVE_TYPE_OPTIONS = ['.zip', '.tgz', '.tar.gz']
</script>
