<template>
	<Dialog
		v-if="alias?.doc"
		v-model="show"
		:options="{
			title: aliasID,
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled:
						JSON.stringify(alias.doc) === JSON.stringify(alias.originalDoc) ||
						!alias.doc.alias_for_name,
					onClick: alias.save.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<Switch v-model="alias.doc.enabled" :label="__('Enabled')" class="switch" />
				<FormControl
					v-model="alias.doc.alias_for_type"
					type="select"
					:label="__('Alias For')"
					:options="[
						{ label: __('User'), value: 'Mail Account' },
						{ label: __('Mailing List'), value: 'Mailing List' },
					]"
				/>
				<LinkControl
					v-model="alias.doc.alias_for_name"
					:label="
						__(alias.doc.alias_for_type === 'Mail Account' ? 'User' : 'Mailing List')
					"
					:doctype="
						alias.doc.alias_for_type === 'Mail Account'
							? 'Mail Account'
							: 'Mailing List'
					"
					:filters="{ tenant: user.data.tenant, enabled: 1 }"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { inject, ref, watch } from 'vue'
import { Dialog, FormControl, Switch, createDocumentResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import LinkControl from '@/components/Controls/LinkControl.vue'

import type { MailAlias } from '@/types'

const show = defineModel<boolean>()

const { aliasID } = defineProps<{ aliasID: string }>()

const emit = defineEmits(['reloadAliases'])

const user = inject('$user')

const alias = ref()

const getAlias = () =>
	createDocumentResource({
		doctype: 'Mail Alias',
		name: aliasID,
		transform: (data: MailAlias) => {
			data.enabled = !!data.enabled
		},
		setValue: {
			onSuccess: () => {
				show.value = false
				raiseToast(__('Alias updated.'))
				emit('reloadAliases')
			},
			onError: (error) => {
				raiseToast(error.messages[0], 'error')
				alias.value.reload()
			},
		},
	})

watch(
	show,
	(val) => {
		if (val) alias.value = getAlias()
	},
	{ immediate: true },
)

watch(
	() => alias.value.doc?.alias_for_type,
	(val) => {
		if (val) alias.value.doc.alias_for_name = ''
	},
)
</script>

<style>
.switch {
	@apply active:bg-surface-white hover:bg-surface-white cursor-auto !p-0;
}
</style>
