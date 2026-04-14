<template>
	<div class="flex items-center justify-between">
		<h1>{{ __('Sieve Scripts') }}</h1>
		<Button icon-left="plus" :label="__('New')" @click="showAddScript = true" />
	</div>

	<div v-if="scripts?.data?.length">
		<div class="text-ink-gray-5 flex gap-4 py-2 text-sm">
			<div class="flex-1">{{ __('Script Name') }}</div>
			<div class="w-24 text-center">{{ __('Status') }}</div>
		</div>
		<div
			v-for="script in scripts?.data"
			:key="script.name"
			class="flex items-center justify-between border-t py-2"
		>
			<div class="flex flex-1 items-center gap-2">
				<span class="text-base">{{ script._name }}</span>
			</div>
			<div class="flex w-24 items-center justify-center">
				<Badge
					:variant="script.active ? 'subtle' : 'outline'"
					:theme="script.active ? 'green' : 'gray'"
					:label="script.active ? __('Active') : __('Inactive')"
					size="md"
				/>
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
	<EditSieveScriptModal
		v-model="showEditScript"
		:script-name="selectedScript"
		@reload-scripts="scripts.reload()"
	/>
	<ViewSieveScriptModal v-model="showViewScript" :script-name="selectedScript" />
</template>

<script setup lang="ts">
import { inject, ref } from 'vue'
import { Ellipsis } from 'lucide-vue-next'
import { Badge, Button, Dropdown, useList } from 'frappe-ui'

import AddSieveScriptModal from '@/components/Modals/AddSieveScriptModal.vue'
import EditSieveScriptModal from '@/components/Modals/EditSieveScriptModal.vue'
import ViewSieveScriptModal from '@/components/Modals/ViewSieveScriptModal.vue'

const user = inject('$user')

const showAddScript = ref(false)
const selectedScript = ref('')
const showEditScript = ref(false)
const showViewScript = ref(false)

const scripts = useList({
	doctype: 'Sieve Script',
	immediate: true,
	fields: ['name', '_name', 'active', 'id'],
	filters: { user: user.data.name },
	cacheKey: ['sieveScripts', user.data.name],
})

const scriptOptions = (script: any) => [
	{
		label: __('View'),
		onClick: () => {
			selectedScript.value = script.name
			showViewScript.value = true
		},
	},
	{
		label: __('Edit'),
		onClick: () => {
			selectedScript.value = script.name
			showEditScript.value = true
		},
	},
	{
		label: script.active ? __('Deactivate') : __('Activate'),
		onClick: async () => {
			await scripts.setValue.submit({
				name: script.name,
				fieldname: 'active',
				value: !script.active,
			})
			scripts.reload()
		},
	},
	{
		label: __('Delete'),
		onClick: () => scripts.delete.submit({ name: script.name }),
		condition: () => !script.active,
	},
]
</script>
