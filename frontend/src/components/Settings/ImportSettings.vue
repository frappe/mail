<template>
	<h1>{{ __('Import Mail') }}</h1>
	<FormControl
		v-model="mailDataImport.import_format"
		:label="__('Format')"
		type="select"
		variant="outline"
		:options="['jmap', 'mbox', 'maildir', 'maildir-nested']"
	/>
	<FileUploader
		:file-types="['.zip', '.tgz', '.tar.gz']"
		:upload-args="{ private: true }"
		@success="(file) => (mailDataImport.import_file = file.file_url)"
	>
		<template #default="{ openFileSelector }">
			<Button class="w-full" :label="__('Upload File')" @click="openFileSelector" />
			<p class="text-ink-gray-5 mt-2 flex text-sm">
				{{
					mailDataImport.import_file
						? __('File uploaded: {0}', [mailDataImport.import_file])
						: __(' Supported file formats: .zip, .tar, .tgz')
				}}
			</p>
		</template>
	</FileUploader>

	<Button
		class="min-h-7"
		:label="__('Create Import')"
		:disabled="!!noOfActiveImports || !mailDataImport.import_file"
		@click="createMailDataImport.submit()"
	/>
	<div v-if="noOfActiveImports" class="text-ink-gray-5 flex items-center space-x-1.5">
		<LoaderCircle class="h-4 w-4 animate-spin" />
		<span class="text-sm"> {{ activeImportMessage }} </span>
	</div>
	<ErrorMessage
		v-if="createMailDataImport.error"
		:message="createMailDataImport.error"
		class="mb-2.5"
	/>
	<span v-if="mailDataImports.data?.length">
		<a class="text-ink-gray-5 cursor-pointer text-sm hover:underline" @click="openImports">
			{{ __('View All Imports') }}
		</a>
	</span>
</template>

<script setup lang="ts">
import { computed, inject, reactive } from 'vue'
import { LoaderCircle } from 'lucide-vue-next'
import {
	Button,
	ErrorMessage,
	FileUploader,
	FormControl,
	createResource,
	useList,
} from 'frappe-ui'

const user = inject('$user')

const mailDataImport = reactive({
	operation: 'Import',
	import_format: 'jmap',
	import_file: '',
})

const createMailDataImport = createResource({
	url: 'mail.api.account.create_mail_data_exchange',
	makeParams: () => mailDataImport,
	onSuccess: () => mailDataImports.reload(),
})

const mailDataImports = useList({
	doctype: 'Mail Data Exchange',
	immediate: true,
	fields: ['name', 'operation', 'status'],
	filters: { user: user.data.name, operation: 'Import' },
	limit: 1000,
})

const noOfActiveImports = computed(
	() =>
		mailDataImports.data?.filter((d) => ['Queued', 'In Progress'].includes(d.status))
			?.length || 0,
)

const activeImportMessage = computed(() =>
	__("Your mail data import is in progress. You'll receive an email once it's complete."),
)

const openImports = () => window.open('/mail/mail-data-exchanges', '_blank')
</script>
