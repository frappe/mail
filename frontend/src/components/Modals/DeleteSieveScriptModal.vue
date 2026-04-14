<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Delete Sieve Script'),
			message: __(
				`Are you sure you want to delete '{0}'? This will remove all associated filters and rules.`,
				[script._name],
			),
			icon: { name: 'alert-triangle', appearance: 'warning' },
			actions: [
				{
					label: __('Confirm'),
					variant: 'solid',
					theme: 'red',
					onClick: () => deleteScript.submit(),
				},
			],
		}"
	/>
</template>

<script setup lang="ts">
import { Dialog, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'

import type { SieveScript } from '@/types'

const show = defineModel<boolean>()
const { script } = defineProps<{ script?: SieveScript }>()
const emit = defineEmits(['reloadScripts'])

const deleteScript = createResource({
	url: 'mail.api.account.delete_sieve_script',
	makeParams: () => ({ name: script.name }),
	onSuccess: () => {
		raiseToast(__('Sieve script deleted.'))
		emit('reloadScripts')
		show.value = false
	},
	onError: (error) => raiseToast(error.message, 'error'),
})
</script>
