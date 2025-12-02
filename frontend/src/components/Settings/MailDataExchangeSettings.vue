<template>
	<h1>{{ __('Mail Data Exchange') }}</h1>
	<FormControl
		v-model="mailDataExchange.operation"
		:label="__('Operation')"
		type="select"
		variant="outline"
		:options="['Import', 'Export']"
	/>

	<template v-if="mailDataExchange.operation === 'Import'">
		<FormControl
			v-model="mailDataExchange.import_format"
			:label="__('Format')"
			type="select"
			variant="outline"
			:options="['jmap', 'mbox', 'maildir', 'maildir-nested']"
		/>
		<FileUploader
			:file-types="['.zip', '.tgz', '.tar.gz']"
			:upload-args="{ private: true }"
			@success="(file) => (mailDataExchange.import_file = file.file_url)"
		>
			<template #default="{ openFileSelector }">
				<Button class="w-full" :label="__('Upload File')" @click="openFileSelector" />
				<p class="text-ink-gray-5 mt-2 flex text-sm">
					{{
						mailDataExchange.import_file
							? __('File uploaded: {0}', [mailDataExchange.import_file])
							: __(' Supported file formats: .zip, .tar, .tgz')
					}}
				</p>
			</template>
		</FileUploader>
	</template>

	<FormControl
		v-else
		v-model="mailDataExchange.export_archive_type"
		:label="__('Archive Type')"
		type="select"
		:options="['.zip', '.tgz', '.tar.gz']"
	/>

	<Button
		class="min-h-7"
		:label="
			mailDataExchange.operation === 'Import' ? __('Create Import') : __('Create Export')
		"
		:disabled="
			!!noOfActiveOperations ||
			(mailDataExchange.operation === 'Import' && !mailDataExchange.import_file)
		"
		@click="createMailDataExchange.submit()"
	/>
	<div v-if="noOfActiveOperations" class="text-ink-gray-5 flex items-center space-x-1.5">
		<LoaderCircle class="h-4 w-4 animate-spin" />
		<span class="text-sm"> {{ activeOperationMessage }} </span>
	</div>
	<ErrorMessage
		v-if="createMailDataExchange.error"
		:message="createMailDataExchange.error"
		class="mb-2.5"
	/>
	<span v-if="mailDataExchanges.data?.length">
		<a class="text-ink-gray-5 cursor-pointer text-sm hover:underline" @click="openOperations">
			{{ __('View All Operations') }}
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

const mailDataExchange = reactive({
	operation: 'Import',
	import_format: 'jmap',
	import_file: '',
	export_archive_type: '.zip',
})

const createMailDataExchange = createResource({
	url: 'mail.api.account.create_mail_data_exchange',
	makeParams: () => mailDataExchange,
	onSuccess: () => mailDataExchanges.reload(),
})

const mailDataExchanges = useList({
	doctype: 'Mail Data Exchange',
	immediate: true,
	fields: ['name', 'operation', 'status'],
	filters: { account: user.data.name },
	limit: 1000,
})

const noOfActiveOperations = computed(
	() =>
		mailDataExchanges.data?.filter(
			(d) =>
				d.operation === mailDataExchange.operation &&
				['Queued', 'In Progress'].includes(d.status),
		)?.length || 0,
)

const activeOperationMessage = computed(() =>
	__('Your mail data {0} is in progress. You’ll receive an email once it’s complete.', [
		mailDataExchange.operation === 'Import' ? __('import') : __('export'),
	]),
)

const openOperations = () => window.open('/mail/mail-data-exchanges', '_blank')
</script>
