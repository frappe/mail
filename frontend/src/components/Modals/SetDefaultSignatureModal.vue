<template>
	<Dialog v-model="show" :options="addSignatureOptions">
		<template #body-content>
			<div class="mb-4 space-y-1.5">
				<label class="text-ink-gray-5 block text-xs"> {{ __('Identity') }} </label>
				<Combobox
					v-model="identity"
					variant="outline"
					:options="
						identities.data.map((identity: Identity) => ({
							label: identity.email,
							value: identity.name,
						}))
					"
					:open-on-click="true"
				/>
			</div>
			<div class="space-y-1.5">
				<label class="text-ink-gray-5 block text-xs"> {{ __('Signature') }} </label>
				<TextEditor
					editor-class="prose-sm min-h-[8rem] border rounded p-2 max-w-none border-outline-gray-2"
					:extensions="[CustomParagraphExtension]"
					:placeholder="__('Write your signature here')"
					:content="signature"
					:editable="false"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Combobox, Dialog, TextEditor, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { CustomParagraphExtension } from '@/utils/text-editor'
import { userStore } from '@/stores/user'

import type { Identity } from '@/types'

const { identities } = userStore()

const show = defineModel<boolean>()

const { signature } = defineProps<{ signature: string }>()

const identity = ref(identities?.data[0]?.name || '')

const addSignatureOptions = computed(() => ({
	title: __('Set Default Signature'),
	actions: [
		{
			label: __('Save'),
			variant: 'solid',
			disabled: !identity.value,
			onClick: () => {
				setSignature.submit()
				show.value = false
			},
		},
	],
}))

const setSignature = createResource({
	url: 'mail.api.account.set_signature',
	makeParams: () => ({ identity: identity.value, signature }),
	onSuccess: () => {
		raiseToast(__('Identity updated.'))
		identities.reload()
	},
	onError: (error) => raiseToast(error.message, 'error'),
})
</script>
