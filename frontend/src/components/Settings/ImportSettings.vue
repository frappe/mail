<template>
	<h1>{{ __('Import Mail') }}</h1>
	<FormControl
		v-model="mailImport.format"
		:label="__('Format')"
		type="select"
		variant="outline"
		:options="['eml', 'jmap', 'mbox', 'maildir', 'maildir-nested']"
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
			:options="[
				{ label: __('Yes'), value: true },
				{ label: __('No'), value: false },
			]"
		/>
	</template>
	<FileUploader
		:file-types="['.zip', '.tgz', '.tar.gz']"
		:upload-args="{ private: true }"
		@success="(file) => (mailImport.file = file.file_url)"
	>
		<template #default="{ openFileSelector }">
			<Button class="w-full" :label="__('Upload File')" @click="openFileSelector" />
			<p class="text-ink-gray-5 mt-2 flex text-sm">
				{{
					mailImport.file
						? __('File uploaded: {0}', [mailImport.file])
						: __(' Supported file formats: .zip, .tar, .tgz')
				}}
			</p>
		</template>
	</FileUploader>

	<Button
		class="min-h-7"
		:label="__('Create Import')"
		:disabled="!!mailImports.data?.length || !mailImport.file"
		@click="createMailImport.submit()"
	/>
	<div v-if="mailImports.data?.length" class="text-ink-gray-5 flex items-center space-x-1.5">
		<LoaderCircle class="h-4 w-4 animate-spin" />
		<span class="text-sm"> {{ ACTIVE_IMPORT_MESSAGE }} </span>
	</div>
	<ErrorMessage v-if="createMailImport.error" :message="createMailImport.error" class="mb-2.5" />
	<a
		v-if="mailImports.data?.length"
		class="text-ink-gray-5 cursor-pointer text-sm hover:underline"
		href="/mail/mail-exchanges"
		target="_blank"
	>
		{{ __('View All Imports') }}
	</a>
</template>

<script setup lang="ts">
import { computed, inject, reactive, watch } from 'vue'
import { LoaderCircle } from 'lucide-vue-next'
import {
	Button,
	ErrorMessage,
	FileUploader,
	FormControl,
	createResource,
	useList,
} from 'frappe-ui'

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
	onSuccess: () => mailImports.reload(),
})

const mailImports = useList({
	doctype: 'Mail Exchange',
	immediate: true,
	fields: ['name'],
	filters: {
		user: user.data.name,
		operation: 'Import',
		status: ['in', ['Queued', 'In Progress']],
	},
	limit: 1,
})

const ACTIVE_IMPORT_MESSAGE = __(
	"Your mail import is in progress. You'll receive an email once it's complete.",
)
</script>
