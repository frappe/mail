<template>
	<div class="flex items-center justify-between">
		<h1>{{ __('Sieve Scripts') }}</h1>
		<Button icon-left="plus" :label="__('New')" @click="showAddScript = true" />
	</div>

	<div v-if="filteredScripts.length">
		<div class="text-ink-gray-5 py-2 text-sm">{{ __('Script Name') }}</div>
		<div
			v-for="script in filteredScripts"
			:key="script.name"
			class="flex items-center justify-between border-t py-1"
		>
			<div class="flex items-center gap-2">
				<span class="text-base">{{ script._name }}</span>
				<Badge v-if="script.active" :label="__('Active')" theme="blue" size="sm" />
			</div>
			<Dropdown :options="scriptOptions(script)">
				<Button variant="ghost" @click.stop>
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

	<AddSieveScriptModal v-model="showAddScript" @reload-scripts="scripts.reload()" />
	<SetSieveScriptStateModal
		v-if="selectedScript"
		v-model="showSetScriptAsActive"
		:script="selectedScript"
		:current-active-script="scripts.data.find((s) => s.active)"
		@reload-scripts="scripts.reload()"
	/>
	<EditSieveScriptModal
		v-model="showEditScript"
		:script="selectedScript"
		@reload-scripts="scripts.reload()"
	/>
	<DeleteSieveScriptModal
		v-if="selectedScript"
		v-model="showDeleteScript"
		:script="selectedScript"
		@reload-scripts="scripts.reload()"
	/>
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { Ellipsis } from 'lucide-vue-next'
import { Badge, Button, Dropdown, createResource } from 'frappe-ui'

import AddSieveScriptModal from '@/components/Modals/AddSieveScriptModal.vue'
import DeleteSieveScriptModal from '@/components/Modals/DeleteSieveScriptModal.vue'
import EditSieveScriptModal from '@/components/Modals/EditSieveScriptModal.vue'
import SetSieveScriptStateModal from '@/components/Modals/SetSieveScriptStateModal.vue'

import type { SieveScript } from '@/types'

const user = inject('$user')

const showAddScript = ref(false)
const selectedScript = ref<SieveScript>()
const showEditScript = ref(false)
const showSetScriptAsActive = ref(false)
const showDeleteScript = ref(false)

const scripts = createResource({
	url: 'mail.api.account.get_sieve_scripts',
	auto: true,
	cache: ['sieveScripts', user.data.name],
})

const filteredScripts = computed(() => scripts.data?.filter((s) => s._name !== 'vacation') || [])

const scriptOptions = (script: SieveScript) => [
	{
		label: script.active ? __('Set as Inactive') : __('Set as Active'),
		onClick: () => {
			selectedScript.value = script
			showSetScriptAsActive.value = true
		},
	},
	{
		label: __('Edit'),
		onClick: () => {
			selectedScript.value = script
			showEditScript.value = true
		},
		condition: () => !script.read_only,
	},
	{
		label: __('Delete'),
		onClick: () => {
			selectedScript.value = script
			showDeleteScript.value = true
		},
		condition: () => !script.read_only,
	},
]
</script>
