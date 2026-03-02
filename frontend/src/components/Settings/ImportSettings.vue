<template>
	<h1>{{ __('Import Mail') }}</h1>
	<FormControl
		v-model="mailImport.format"
		:label="__('Format')"
		type="select"
		variant="outline"
		:options="FORMAT_OPTIONS"
		required
	/>
	<template v-if="['eml', 'maildir'].includes(mailImport.format)">
		<FormControl
			v-model="mailImport.mailbox"
			:label="__('Folder')"
			type="select"
			variant="outline"
			:options="mailboxOptions"
		/>
		<FormControl
			v-model="mailImport.seen"
			:label="__('Mark as Read')"
			type="select"
			variant="outline"
			:options="markAsReadOptions"
		/>
	</template>
	<FileUploader
		:file-types="mailImport.format === 'eml' ? '.eml' : ['.zip', '.tgz', '.tar.gz']"
		:upload-args="{ private: true }"
		@success="(file) => (mailImport.file = file.file_url)"
	>
		<template #default="{ openFileSelector }">
			<Button class="w-full" :label="__('Upload File')" @click="openFileSelector" />
			<p class="text-ink-gray-5 mt-2 flex text-sm">{{ fileUploadSubtitle }}</p>
		</template>
	</FileUploader>

	<Button
		class="min-h-7"
		:label="__('Create Import')"
		variant="solid"
		:loading="ongoingImport.data?.name"
		:disabled="ongoingImport.loading || ongoingImport.error || !mailImport.file"
		@click="createMailImport.submit()"
	/>
	<div class="!mt-3 space-x-1 text-base">
		<span class="text-ink-gray-5">{{ importSubtitle }}</span>
		<a class="hover:underline" :href="importHref" target="_blank">
			{{ importLinkText }}
		</a>
	</div>
	<ErrorMessage v-if="createMailImport.error" :message="createMailImport.error" class="mb-2.5" />
</template>

<script setup lang="ts">
import { computed, inject, reactive, watch } from 'vue'
import { Button, ErrorMessage, FileUploader, FormControl, createResource } from 'frappe-ui'

import { userStore } from '@/stores/user'

const { mailboxes } = userStore()

const user = inject('$user')

const mailImport = reactive({
	format: 'eml',
	file: '',
	mailbox: '',
	seen: false,
})

const mailboxOptions = computed(() =>
	mailboxes.data.map((m: { id: string; _name: string }) => ({
		label: m._name,
		value: m.id,
	})),
)

const markAsReadOptions = computed(() => [
	{ label: __('Yes'), value: true },
	{ label: __('No'), value: false },
])

const fileUploadSubtitle = computed(() => {
	if (mailImport.file) return __('File uploaded: {0}', [mailImport.file])
	if (mailImport.format === 'eml') return __('Supported file format: .eml')
	return __('Supported file formats: .zip, .tar, .tgz')
})

watch(
	mailboxOptions,
	(options) => {
		if (options.length > 0 && !mailImport.mailbox) {
			mailImport.mailbox = options[0].value
		}
	},
	{ immediate: true },
)

const createMailImport = createResource({
	url: 'mail.api.account.create_mail_import',
	makeParams: () => mailImport,
	onSuccess: () => ongoingImport.reload(),
})

const ongoingImport = createResource({
	url: 'frappe.client.get_value',
	auto: true,
	makeParams: () => ({
		doctype: 'Mail Exchange',
		fieldname: 'name',
		filters: {
			user: user.data.name,
			operation: 'Import',
			status: ['in', ['Queued', 'In Progress']],
		},
	}),
})

const importSubtitle = computed(() => {
	if (ongoingImport.data?.name) return __("Import in progress. We'll email you when it's ready.")
	return __('No imports in progress.')
})

const importHref = computed(() => {
	if (ongoingImport.data?.name) return `/mail/mail-exchanges/${ongoingImport.data.name}`
	return '/mail/mail-exchanges'
})

const importLinkText = computed(() => {
	if (ongoingImport.data?.name) return __('Track status')
	return __('View history')
})

const FORMAT_OPTIONS = ['eml', 'jmap', 'mbox', 'maildir', 'maildir-nested']
</script>
