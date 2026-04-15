<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Set Script as {0}', [newState]),
			message,
			icon: { name: 'alert-triangle', appearance: 'warning' },
			actions: [
				{ label: __('Confirm'), variant: 'solid', onClick: () => setScriptState.submit() },
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
const { script, currentActiveScript } = defineProps<{
	script: SieveScript
	currentActiveScript?: string
}>()
const emit = defineEmits(['reloadScripts'])

const newState = computed(() => (script.active ? __('Inactive') : __('Active')))

const message = computed(() => {
	if (newState.value === __('Inactive'))
		return __(
			"Are you sure you want to deactivate '{0}'? This will stop all associated filters and rules from functioning.",
			[script._name],
		)

	if (!currentActiveScript) return __("Are you sure you want to activate '{0}'?", [script._name])

	if (currentActiveScript === 'vacation')
		return __(
			"Vacation Response is currently enabled. Setting '{0}' as active will stop your vacation response from functioning. Are you sure you want to proceed?",
			[script._name],
		)
	return __(
		"'{0}' is currently active. Setting '{1}' as active will deactivate '{0}'. Are you sure you want to proceed?",
		[currentActiveScript, script._name],
	)
})

const setScriptState = createResource({
	url: 'mail.api.account.update_sieve_script',
	makeParams: () => ({ ...script, active: !script.active }),
	onSuccess: () => {
		raiseToast(script.active ? __('Sieve script deactivated.') : __('Sieve script activated.'))
		emit('reloadScripts')
		show.value = false
	},
	onError: (error) => raiseToast(error.message, 'error'),
})
</script>
