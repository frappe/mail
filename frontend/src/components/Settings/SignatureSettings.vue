<template>
	<div class="flex items-center justify-between">
		<h1>{{ __('Signatures') }}</h1>
		<Button icon-left="plus" :label="__('New')" @click="showAddSignature = true" />
	</div>
	<template v-if="signatures?.data?.length">
		<AutocompleteControl
			v-model="defaultSignature"
			variant="outline"
			:label="__('Default Signature')"
			:show-search="false"
			:options="
				signatures?.data?.map((signature) => ({
					label: signature.signature_name,
					value: signature.name,
				}))
			"
		/>

		<div>
			<div class="text-ink-gray-5 pb-2 text-sm">{{ __('Signature Name') }}</div>
			<div
				v-for="signature in signatures?.data"
				:key="signature.name"
				class="flex items-center justify-between border-t py-1"
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
	</template>
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
import { Button, Dropdown } from 'frappe-ui'
import { useList } from 'frappe-ui/src/data-fetching'

import AutocompleteControl from '@/components/Controls/AutocompleteControl.vue'
import AddSignatureModal from '@/components/Modals/AddSignatureModal.vue'
import EditSignatureModal from '@/components/Modals/EditSignatureModal.vue'

const user = inject('$user')

const defaultSignature = ref('')
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
