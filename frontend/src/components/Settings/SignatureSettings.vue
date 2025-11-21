<template>
	<div class="flex items-center justify-between">
		<h1>{{ __('Signatures') }}</h1>
		<Button icon-left="plus" :label="__('New')" @click="showAddSignature = true" />
	</div>
	{{ signatures.data }}

	<Dialog v-model="showAddSignature" :options="addSignatureOptions">
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="newSignature.signature_name"
					:label="__('Signature Name')"
					:placeholder="__('Work signature')"
					variant="outline"
				/>
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Signature Body') }}</label>
					<TextEditor
						editor-class="prose-sm min-h-[8rem] border rounded p-2 max-w-none border-outline-gray-2"
						:extensions="[CustomParagraphExtension]"
						:placeholder="__('Write your signature here')"
						:content="newSignature.html_body"
						@change="(val: string) => (newSignature.html_body = val)"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, inject, reactive, ref, watch } from 'vue'
import { Button, Dialog, FormControl, TextEditor } from 'frappe-ui'
import { useList } from 'frappe-ui/src/data-fetching'

import { CustomParagraphExtension } from '@/utils/text-editor'

const user = inject('$user')

const showAddSignature = ref(false)

const newSignature = reactive({
	account: user.data.name,
	signature_name: '',
	html_body: '',
})

const signatures = useList({
	doctype: 'Mail Signature',
	immediate: true,
	fields: ['name', 'signature_name', 'html_body'],
	filters: { account: user.data.name },
	cacheKey: ['mailSignatures', user.data.name],
})

const addSignatureOptions = computed(() => ({
	title: __('New Signature'),
	actions: [
		{
			label: __('Save'),
			variant: 'solid',
			onClick: () => {
				signatures.insert.submit(newSignature)
				showAddSignature.value = false
			},
		},
	],
}))

watch(showAddSignature, (val) => {
	if (!val) return
	newSignature.signature_name = ''
	newSignature.html_body = ''
})
</script>
