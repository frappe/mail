<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Add Domain'),
			actions: [
				{
					label: domainRequest?.data ? __('Verify DNS') : __('Add Domain'),
					variant: 'solid',
					onClick: domainRequest?.data ? verifyDNS.submit : domainRequest.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<p class="text-p-base">
					{{
						__(
							`To add a domain, you must already own it. If you don't have one, purchase one and return here.`,
						)
					}}
				</p>
				<FormControl
					v-model="domainName"
					:label="__('Domain Name')"
					placeholder="example.com"
					:readonly="!!domainRequest?.data"
					autocomplete="off"
				/>
				<ErrorMessage :message="domainRequest.error?.messages[0]" />
				<div v-if="domainRequest.data?.verification_key" class="space-y-4">
					<p class="text-p-base">
						{{
							__(
								`Add the following TXT record to your domain's DNS records to verify your ownership:`,
							)
						}}
					</p>
					<CopyControl
						:label="__('Verification Key')"
						:value="domainRequest.data.verification_key"
					/>
					<ErrorMessage :message="verifyDNS.error?.messages[0] || verificationError" />
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import CopyControl from '@/components/Controls/CopyControl.vue'

const show = defineModel<boolean>()

const domainName = ref('')
const verificationError = ref('')

const emit = defineEmits(['reloadDomains'])

watch(show, () => {
	if (show.value) {
		domainName.value = ''
		verificationError.value = ''
		domainRequest.reset()
		verifyDNS.reset()
	}
})

const domainRequest = createResource({
	url: 'mail.api.admin.get_domain_request',
	makeParams: () => ({ domain_name: domainName.value }),
})

const verifyDNS = createResource({
	url: 'mail.api.admin.verify_dns_record',
	makeParams: () => ({ domain_request: domainRequest?.data.name }),
	onSuccess: (data) => {
		if (data) {
			show.value = false
			emit('reloadDomains')
			raiseToast('Domain added.')
		} else verificationError.value = __('Failed to verify DNS record.')
	},
})
</script>
