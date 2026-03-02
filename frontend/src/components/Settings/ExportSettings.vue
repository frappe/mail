<template>
	<h1>{{ __('Export Mail') }}</h1>
	<FormControl
		v-model="mailExport.format"
		:label="__('Format')"
		type="select"
		variant="outline"
		:options="['jmap', 'mbox', 'maildir', 'maildir-nested']"
	/>
	<FormControl
		v-model="mailExport.archive_type"
		:label="__('Archive Type')"
		type="select"
		variant="outline"
		:options="['.zip', '.tgz', '.tar.gz']"
	/>
	<FormControl
		v-model="mailExport.sort"
		:label="__('Sort By')"
		type="select"
		variant="outline"
		:options="[
			{ label: __('Received At (ASC)'), value: 'Received At (ASC)' },
			{ label: __('Received At (DESC)'), value: 'Received At (DESC)' },
		]"
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
	</template>

	<Button
		class="min-h-7"
		:label="__('Create Export')"
		:disabled="!!noOfActiveExports"
		@click="createMailExport.submit()"
	/>
	<div v-if="noOfActiveExports" class="text-ink-gray-5 flex items-center space-x-1.5">
		<LoaderCircle class="h-4 w-4 animate-spin" />
		<span class="text-sm"> {{ activeExportMessage }} </span>
	</div>
	<ErrorMessage v-if="createMailExport.error" :message="createMailExport.error" class="mb-2.5" />
	<span v-if="mailExports.data?.length">
		<a class="text-ink-gray-5 cursor-pointer text-sm hover:underline" @click="openExports">
			{{ __('View All Exports') }}
		</a>
	</span>
</template>

<script setup lang="ts">
import { computed, inject, reactive, ref } from 'vue'
import { LoaderCircle } from 'lucide-vue-next'
import { Button, ErrorMessage, FormControl, Switch, createResource, useList } from 'frappe-ui'

import { getAttachmentOptions, getReadStatusOptions } from '@/constants'
import { userStore } from '@/stores/user'

const { mailboxes } = userStore()

const user = inject('$user')

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
	hasAttachment: '',
	isRead: '',
})

const mailboxOptions = computed(() =>
	[{ label: __(''), value: ' ' }].concat(
		mailboxes.data.map((m: { id: string; _name: string }) => ({
			label: m._name,
			value: m.id,
		})),
	),
)

const createMailExport = createResource({
	url: 'mail.api.account.create_mail_export',
	makeParams: () => ({ ...mailExport, filter }),
	onSuccess: () => mailExports.reload(),
})

const mailExports = useList({
	doctype: 'Mail Exchange',
	immediate: true,
	fields: ['name', 'operation', 'status'],
	filters: { user: user.data.name, operation: 'Export' },
	limit: 1000,
})

const noOfActiveExports = computed(
	() =>
		mailExports.data?.filter((d) => ['Queued', 'In Progress'].includes(d.status))?.length || 0,
)

const activeExportMessage = computed(() =>
	__("Your mail data export is in progress. You'll receive an email once it's complete."),
)

const openExports = () => window.open('/mail/mail-data-exchanges', '_blank')
</script>
