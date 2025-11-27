<template>
	<div class="flex items-center justify-between">
		<h1>{{ __('Signatures') }}</h1>
		<Button icon-left="plus" :label="__('New')" @click="showAddSignature = true" />
	</div>
	<div v-if="signatures?.data?.length">
		<div
			v-for="signature in signatures?.data"
			:key="signature.name"
			class="flex items-center justify-between py-1"
		>
			<span class="text-base">{{ signature.signature_name }}</span>
			<Dropdown :options="signatureOptions(signature.name)">
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

const user = inject('$user')

const showAddSignature = ref(false)
const selectedSignature = ref('')
const showEditSignature = ref(false)

const signatures = useList({
	doctype: 'Mail Signature',
	immediate: true,
	fields: ['name', 'signature_name', 'html_body'],
	filters: { account: user.data.name },
	cacheKey: ['mailSignatures', user.data.name],
})

const signatureOptions = (name: string) => [
	{
		label: __('Edit'),
		onClick: () => {
			selectedSignature.value = name
			showEditSignature.value = true
		},
	},
	{
		label: __('Delete'),
		onClick: () => signatures.delete.submit({ name }),
	},
]
</script>
