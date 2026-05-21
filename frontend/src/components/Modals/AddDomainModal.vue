<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Add Domain'),
			actions: [
				{
					label: __('Add Domain'),
					variant: 'solid',
					disabled: !domainName,
					onClick: addDomain.submit,
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
					autocomplete="off"
				/>
				<ErrorMessage
					:message="addDomain.error?.messages[0] || addDomain.error?.message"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, ErrorMessage, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'

const show = defineModel<boolean>()
const router = useRouter()

const domainName = ref('')

const emit = defineEmits(['reloadDomains'])

watch(show, () => {
	if (show.value) {
		domainName.value = ''
		addDomain.reset()
	}
})

const addDomain = createResource({
	url: 'mail.api.admin.add_domain',
	makeParams: () => ({ name: domainName.value }),
	onSuccess: (data: string) => {
		if (!data) return

		show.value = false
		emit('reloadDomains')
		raiseToast(__('Domain added.'))
		router.push({ name: 'Domain', params: { domainId: data } })
	},
})
</script>
