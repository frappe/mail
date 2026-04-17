<template>
	<div class="flex items-center justify-between">
		<h1>{{ __('Signatures') }}</h1>
		<Button icon-left="plus" :label="__('New')" @click="showAddSignature = true" />
	</div>
	<div v-if="signatures?.data?.length">
		<div
			v-for="signature in signatures?.data"
			:key="signature.name"
			class="hover:bg-surface-gray-1 -mx-2 flex cursor-pointer items-center justify-between rounded px-3 py-1"
			@click="editSignature(signature.name)"
		>
			<span class="text-base">{{ signature.signature_name }}</span>
			<Dropdown :options="signatureOptions(signature)">
				<Button variant="" @click.stop>
					<template #icon>
						<Ellipsis class="text-ink-gray-5 h-4 w-4" />
					</template>
				</Button>
			</Dropdown>
		</div>
	</div>

	<div v-else class="text-ink-gray-6 flex flex-col space-y-2 text-sm">
		<p class="text-base font-medium">{{ __('No signatures found.') }}</p>

		<p>
			{{ __('Signatures let you automatically add personalized content to your emails.') }}
		</p>
	</div>

	<AddSignatureModal v-model="showAddSignature" @reload-signatures="signatures.reload()" />
	<SetDefaultSignatureModal v-model="showSetSignature" :signature="selectedSignature" />
	<EditSignatureModal
		v-model="showEditSignature"
		:signature-i-d="selectedSignature"
		@reload-signatures="signatures.reload()"
	/>
</template>

<script setup lang="ts">
import { inject, ref } from 'vue'
import { Edit2, Ellipsis, Pin, Trash2 } from 'lucide-vue-next'
import { Button, Dropdown, useList } from 'frappe-ui'

import AddSignatureModal from '@/components/Modals/AddSignatureModal.vue'
import EditSignatureModal from '@/components/Modals/EditSignatureModal.vue'
import SetDefaultSignatureModal from '@/components/Modals/SetDefaultSignatureModal.vue'

import type { MailSignature } from '@/types'

const user = inject('$user')

const showAddSignature = ref(false)
const selectedSignature = ref('')
const showSetSignature = ref(false)
const showEditSignature = ref(false)

const signatures = useList({
	doctype: 'Mail Signature',
	immediate: true,
	fields: ['name', 'signature_name', 'html_body'],
	filters: { account: user.data.name },
	cacheKey: ['mailSignatures', user.data.name],
})

const editSignature = (signature: string) => {
	selectedSignature.value = signature
	showEditSignature.value = true
}

const signatureOptions = (signature: MailSignature) => [
	{
		label: __('Set Default'),
		icon: Pin,
		onClick: () => {
			selectedSignature.value = signature.html_body!
			showSetSignature.value = true
		},
		condition: () => signature.html_body,
	},
	{
		label: __('Edit'),
		icon: Edit2,
		onClick: () => editSignature(signature.name),
	},
	{
		label: __('Delete'),
		icon: Trash2,
		theme: 'red',
		onClick: () => signatures.delete.submit({ name: signature.name }),
	},
]
</script>
