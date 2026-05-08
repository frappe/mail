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
					:description="__('Activate this script to apply your rules and filters.')"
					class="!p-0"
				/>
				<Alert
					v-if="script.active && activeScript && activeScript !== original._name"
					:title="
						isSystemScript(activeScript)
							? __('{0} Enabled', [getScriptName(activeScript)])
							: __('Active Script {0} Detected', [getScriptName(activeScript)])
					"
					:description="
						isSystemScript(activeScript)
							? __('Activating this script will disable {0}.', [
									getScriptName(activeScript),
								])
							: __(
									'Activating this script will deactivate the currently active script.',
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

import { getScriptName, isSystemScript, raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

import type { SieveScript } from '@/types'

const show = defineModel<boolean>()
const { selectedScript } = defineProps<{ selectedScript?: SieveScript }>()

const store = userStore()
const activeScript = computed(() => store.sieveScripts.data?.find((s) => s.active)?._name)

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
	url: 'mail.api.sieve.create_sieve_script',
	makeParams: () => ({ account: store.account, ...script }),
	onSuccess: () => {
		raiseToast(__('Sieve script created.'))
		store.sieveScripts.reload()
		show.value = false
	},
	onError: (e) => raiseToast(e.messages[0], 'error'),
})

const updateScript = createResource({
	url: 'mail.api.sieve.update_sieve_script',
	makeParams: () => ({ account: store.account, id: selectedScript!.id, ...script }),
	onSuccess: () => {
		raiseToast(__('Sieve script updated.'))
		store.sieveScripts.reload()
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
