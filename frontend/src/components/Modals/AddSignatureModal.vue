<template>
	<Dialog v-model="show" :options="addSignatureOptions">
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="signature.doc.signature_name"
					:label="__('Signature Name')"
					:placeholder="__('Work signature')"
					variant="outline"
				/>
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Signature Body') }}</label>
					<TextEditor
						editor-class="prose-sm min-h-[8rem] border rounded-b-lg border-t-0 p-2 max-w-none border-outline-gray-2"
						:extensions="[CustomParagraphExtension]"
						:fixed-menu="buttons"
						:placeholder="__('Write your signature here')"
						:content="signature.doc.html_body"
						@change="(val: string) => (signature.doc.html_body = val)"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, inject, reactive, watch } from 'vue'
import { Dialog, FormControl, TextEditor, useNewDoc } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { useTextEditorButtons } from '@/utils/composables'
import { CustomParagraphExtension } from '@/utils/text-editor'

const user = inject('$user')

const show = defineModel<boolean>()

const emit = defineEmits(['reloadSignatures'])

const { buttons } = useTextEditorButtons()

const defaultSignature = reactive({
	account: user.data.name,
	signature_name: '',
	html_body: '',
})

const signature = useNewDoc(
	'Mail Signature',
	{ ...defaultSignature },
	{
		onSuccess: () => {
			show.value = false
			raiseToast(__('Signature created.'))
			emit('reloadSignatures')
		},
		onError: (error) => raiseToast(error.message, 'error'),
	},
)

const addSignatureOptions = computed(() => ({
	title: __('New Signature'),
	actions: [
		{
			label: __('Save'),
			variant: 'solid',
			disabled: !signature.doc.signature_name || !signature.doc.html_body,
			onClick: () => {
				signature.submit()
				show.value = false
			},
		},
	],
}))

watch(show, (val) => {
	if (val) Object.assign(signature.doc, defaultSignature)
})
</script>
