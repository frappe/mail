<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Delete Sieve Script'),
			message,
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
import { computed } from 'vue'
import { Dialog, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'

import type { SieveScript } from '@/types'

const show = defineModel<boolean>()
const { script } = defineProps<{ script: SieveScript }>()
const emit = defineEmits(['reloadScripts'])

const message = computed(() => {
	if (script.active)
		return __(
			"'{0}' is currently active. Deleting it will stop all associated filters and rules from functioning. Are you sure you want to proceed?",
			[script._name],
		)
	return __("Are you sure you want to delete '{0}'? ", [script._name])
})

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
