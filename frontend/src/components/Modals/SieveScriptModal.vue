<template>
	<Dialog
		v-model="show"
		:options="{
			title: selectedScript ? __('Edit Sieve Script') : __('New Sieve Script'),
			size: '3xl',
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled: !script._name || !script.content || (selectedScript && isNotDirty),
					onClick: () =>
						selectedScript ? updateScript.submit() : createScript.submit(),
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="script._name" :label="__('Script Name')" required />
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">
						{{ __('Script Content') }}
					</label>
					<FormControl
						v-model="script.content"
						type="textarea"
						:rows="20"
						required
						class="font-mono"
					/>
				</div>

				<hr />
				<Switch
					v-model="script.active"
					:label="__('Activate Script')"
					:description="__('Enable this script to start filtering emails.')"
					class="!p-0"
				/>
				<Alert
					v-if="script.active && activeScript && activeScript !== script._name"
					:title="
						activeScript === 'vacation'
							? __('Vacation Response Active')
							: __('Active Script Detected')
					"
					:description="
						activeScript === 'vacation'
							? __(
									'Vacation response is currently enabled. Activating this will turn it off.',
								)
							: __(
									`Script '{0}' is currently active. Only one script can be active at a time. Activating this will turn off the current active script.`,
									[activeScript],
								)
					"
					theme="yellow"
					:dismissable="false"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Alert, Dialog, FormControl, Switch, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

import type { SieveScript } from '@/types'

const show = defineModel<boolean>()
const { selectedScript } = defineProps<{ selectedScript?: SieveScript }>()

const { sieveScripts } = userStore()
const activeScript = computed(() => sieveScripts.data?.find((s) => s.active)?._name)

const DEFAULT_SCRIPT = { _name: '', content: '', active: false }

const script = reactive({ ...DEFAULT_SCRIPT })
const original = reactive({ ...DEFAULT_SCRIPT })

const isNotDirty = computed(
	() =>
		script._name === original._name &&
		script.content === original.content &&
		script.active === original.active,
)

const createScript = createResource({
	url: 'mail.api.account.create_sieve_script',
	makeParams: () => script,
	onSuccess: () => {
		raiseToast(__('Sieve script created.'))
		sieveScripts.reload()
		show.value = false
	},
	onError: (e) => raiseToast(e.messages[0], 'error'),
})

const updateScript = createResource({
	url: 'mail.api.account.update_sieve_script',
	makeParams: () => ({ name: selectedScript!.name, ...script }),
	onSuccess: () => {
		raiseToast(__('Sieve script updated.'))
		sieveScripts.reload()
		show.value = false
	},
	onError: (e) => raiseToast(e.messages[0], 'error'),
})

watch(show, (val) => {
	if (!val) {
		Object.assign(script, DEFAULT_SCRIPT)
		Object.assign(original, DEFAULT_SCRIPT)
	} else if (selectedScript) {
		script._name = original._name = selectedScript._name
		script.content = original.content = selectedScript.content
		script.active = original.active = !!selectedScript.active
	}
})
</script>
