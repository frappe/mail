<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('New Mailing List'),
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled: !(list.doc.username && list.doc.domain_name),
					onClick: list.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div class="mb-4 flex items-center justify-between">
				<FormControl
					v-model="list.doc.username"
					:label="__('Username')"
					placeholder="team"
					class="w-full"
				/>
				<FeatherIcon
					class="text-ink-gray-3 mx-2.5 mb-1.5 mt-auto h-4 w-4"
					name="at-sign"
				/>
				<LinkControl
					v-model="list.doc.domain_name"
					:label="__('Domain Name')"
					placeholder="yourdomain.com"
					doctype="Mail Domain"
					:filters="{ tenant: user.data.tenant, is_verified: 1 }"
					class="w-full"
				/>
			</div>
			<FormControl
				v-model="list.doc.display_name"
				:label="__('Display Name')"
				placeholder="Team Example"
			/>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { inject, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, FeatherIcon, FormControl, useNewDoc } from 'frappe-ui'

import { raiseToast } from '@/utils'
import LinkControl from '@/components/Controls/LinkControl.vue'

const show = defineModel<boolean>()

const user = inject('$user')
const router = useRouter()

const defaultList = {
	username: '',
	domain_name: '',
	display_name: '',
}

const list = useNewDoc(
	'Mailing List',
	{ ...defaultList },
	{
		beforeSubmit: () => {
			list.doc.email = `${list.doc.username}@${list.doc.domain_name}`
		},
		onSuccess: () => {
			show.value = false
			raiseToast(__('Mailing List created successfully'))
			router.push({ name: 'MailingList', params: { listName: list.doc.email } })
		},
		onError: (error) => raiseToast(error.message, 'error'),
	},
)

watch(show, (val) => {
	if (val) Object.assign(list.doc, defaultList)
})
</script>
