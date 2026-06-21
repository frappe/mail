<template>
	<div class="sm:bg-surface-gray-1 min-h-screen py-4 sm:py-12">
		<div
			class="bg-surface-white mx-auto max-w-full space-y-6 rounded-md border p-4 sm:w-[75rem] sm:space-y-8 sm:p-12"
		>
			<template v-if="mime.data">
				<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
					<h1 class="text-xl !font-medium">{{ __('MIME Message') }}</h1>
					<Button
						:label="__('Copy to Clipboard')"
						size="md"
						@click="copyToClipBoard(message)"
					/>
				</div>
				<div class="rounded-md border">
					<div class="border-b px-4 py-4 sm:px-6">
						<h2>{{ __('Message Information') }}</h2>
					</div>
					<div
						v-for="[key, value] of Object.entries(mime.data)"
						:key="key"
						class="even:bg-surface-gray-1 flex flex-col gap-1 px-4 py-4 text-base last:rounded-b sm:flex-row sm:items-center sm:px-6"
					>
						<div class="text-ink-gray-5 w-full sm:w-1/4">{{ value.label }}</div>
						<div class="flex w-full items-center break-words sm:w-3/4">{{ value.value }}</div>
					</div>
				</div>
				<pre
					class="overflow-x-auto whitespace-pre-wrap break-words"
					style="font-size: 0.875rem"
				>{{ message }}</pre>
			</template>

			<div v-else-if="mime.error" class="space-y-4 text-center">
				<h1 class="text-xl !font-medium text-red-500">{{ __('Error') }}</h1>
				<div class="text-ink-gray-5" v-html="mime.error.messages[0]" />
				<Button :label="__('Return to Home')" size="md" @click="$router.push('/')" />
			</div>
		</div>
	</div>
</template>

<script lang="ts" setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { Button, createResource } from 'frappe-ui'

import { copyToClipBoard } from '@/utils'

const route = useRoute()
const message = ref('')

interface MimeField {
	label: string
	value: string
}

interface Mime {
	message?: string
	message_id: MimeField
	created_at: MimeField
	subject: MimeField
	from: MimeField
	to: MimeField
	cc?: MimeField
	bcc?: MimeField
	spf?: MimeField
	dkim?: MimeField
	dmarc?: MimeField
}

const mime = createResource({
	url: 'mail.api.mail.get_mime_message',
	auto: true,
	makeParams: () => ({ name: route.params.id }),
	transform: (data: Mime) => {
		message.value = data.message as string
		delete data.message
		if (data.cc && !data.cc.value) delete data.cc
		if (data.bcc && !data.bcc.value) delete data.bcc
	},
})
</script>
