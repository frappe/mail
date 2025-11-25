<template>
	<Dialog v-if="signature?.doc" v-model="show" :options="addSignatureOptions">
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
import { computed, ref, watch } from 'vue'
import { Dialog, FormControl, TextEditor, createDocumentResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { useTextEditorButtons } from '@/utils/composables'
import { CustomParagraphExtension } from '@/utils/text-editor'

const show = defineModel<boolean>()

const { signatureID } = defineProps<{ signatureID: string }>()

const emit = defineEmits(['reloadSignatures'])

const { buttons } = useTextEditorButtons()

const signature = ref()

const getSignature = () =>
	createDocumentResource({
		doctype: 'Mail Signature',
		name: signatureID,
		setValue: {
			onSuccess: () => {
				show.value = false
				raiseToast(__('Signature updated successfully'))
				emit('reloadSignatures')
			},
			onError: (error) => {
				raiseToast(error.messages[0], 'error')
				signature.value.reload()
			},
		},
	})

const addSignatureOptions = computed(() => ({
	title: __('New Signature'),
	actions: [
		{
			label: __('Save'),
			variant: 'solid',
			disabled: !signature.value.doc.signature_name || !signature.value.doc.html_body,
			onClick: () => {
				signature.value.save.submit()
				show.value = false
			},
		},
	],
}))

watch(
	show,
	(val) => {
		if (val) signature.value = getSignature()
	},
	{ immediate: true },
)
</script>
