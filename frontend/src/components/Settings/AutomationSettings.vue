<template>
	<div class="flex items-center justify-between">
		<h1>{{ __('Sieve Scripts') }}</h1>
		<Button icon-left="plus" :label="__('New')" @click="addScript" />
	</div>

	<div v-if="filteredScripts.length">
		<div
			v-for="script in filteredScripts"
			:key="script.name"
			class="hover:bg-surface-gray-1 -mx-2 flex cursor-pointer items-center justify-between rounded px-3 py-1"
			@click="editScript(script)"
		>
			<div class="flex items-center gap-2">
				<span class="text-base">{{ script._name }}</span>
				<Badge v-if="script.active" :label="__('Active')" theme="blue" size="sm" />
			</div>
			<Dropdown :options="scriptOptions(script)">
				<Button variant="" @click.stop>
					<template #icon>
						<Ellipsis class="text-ink-gray-5 h-4 w-4" />
					</template>
				</Button>
			</Dropdown>
		</div>
	</div>

	<div v-else class="text-ink-gray-6 flex flex-col space-y-2 text-sm">
		<p class="text-base font-medium">{{ __('No sieve scripts found.') }}</p>
		<div class="space-x-1">
			<span>
				{{
					__('Sieve scripts let you automatically filter and organize incoming emails.')
				}}
			</span>
			<a
				class="text-ink-blue-2 hover:underline"
				href="https://stalw.art/docs/category/sieve-scripting/"
				target="_blank"
			>
				{{ __('Learn more.') }}
			</a>
		</div>
	</div>

	<SieveScriptModal v-model="showSieveScript" :selected-script />
	<SetSieveScriptStateModal
		v-if="selectedScript"
		v-model="showSetScriptAsActive"
		:script="selectedScript"
	/>
	<DeleteSieveScriptModal
		v-if="selectedScript"
		v-model="showDeleteScript"
		:script="selectedScript"
	/>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Ellipsis } from 'lucide-vue-next'
import { Badge, Button, Dropdown } from 'frappe-ui'

import { userStore } from '@/stores/user'
import DeleteSieveScriptModal from '@/components/Modals/DeleteSieveScriptModal.vue'
import SetSieveScriptStateModal from '@/components/Modals/SetSieveScriptStateModal.vue'
import SieveScriptModal from '@/components/Modals/SieveScriptModal.vue'

import type { SieveScript } from '@/types'

const { sieveScripts } = userStore()

const showSieveScript = ref(false)
const selectedScript = ref<SieveScript>()
const showSetScriptAsActive = ref(false)
const showDeleteScript = ref(false)

const filteredScripts = computed(
	() =>
		sieveScripts.data?.filter((s) => !s.read_only && s._name !== 'frappe_mail_automation') ||
		[],
)

const addScript = () => {
	selectedScript.value = undefined
	showSieveScript.value = true
}

const editScript = (script: SieveScript) => {
	selectedScript.value = script
	showSieveScript.value = true
}

const scriptOptions = (script: SieveScript) => [
	{
		label: script.active ? __('Deactivate') : __('Activate'),
		icon: script.active ? 'eye-off' : 'eye',
		onClick: () => {
			selectedScript.value = script
			showSetScriptAsActive.value = true
		},
	},
	{
		label: __('Edit'),
		icon: 'edit-2',
		onClick: () => editScript(script),
	},
	{
		label: __('Delete'),
		icon: 'trash-2',
		theme: 'red',
		onClick: () => {
			selectedScript.value = script
			showDeleteScript.value = true
		},
		condition: () => !script.active,
	},
]
</script>
