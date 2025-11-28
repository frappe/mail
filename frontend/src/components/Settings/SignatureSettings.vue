<template>
	<div class="flex items-center justify-between">
		<h1>{{ __('Signatures') }}</h1>
		<Button icon-left="plus" :label="__('New')" @click="showAddSignature = true" />
	</div>
	<div v-if="signatures?.data?.length">
		<div class="text-ink-gray-5 py-2 text-sm">{{ __('Signature Name') }}</div>
		<div
			v-for="signature in signatures?.data"
			:key="signature.name"
			class="flex items-center justify-between border-t py-1"
		>
			<span class="text-base">{{ signature.signature_name }}</span>
			<Dropdown :options="signatureOptions(signature)">
				<Button variant="ghost" @click.stop>
					<template #icon>
						<Ellipsis class="text-ink-gray-5 h-4 w-4" />
					</template>
				</Button>
			</Dropdown>
		</div>
	</div>

	<div v-else class="text-ink-gray-5 text-sm">{{ __('No signatures found.') }}</div>

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
import { Ellipsis } from 'lucide-vue-next'
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

const signatureOptions = (signature: MailSignature) => [
	{
		label: __('Set Default'),
		onClick: () => {
			selectedSignature.value = signature.html_body!
			showSetSignature.value = true
		},
		condition: () => signature.html_body,
	},
	{
		label: __('Edit'),
		onClick: () => {
			selectedSignature.value = signature.name
			showEditSignature.value = true
		},
	},
	{
		label: __('Delete'),
		onClick: () => signatures.delete.submit({ name: signature.name }),
	},
]
</script>
