<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Add External Member'),
			actions: [
				{
					label: __('Confirm'),
					variant: 'solid',
					disabled: !member.doc.member_email,
					onClick: member.submit,
				},
			],
		}"
	>
		<template #body-content>
			<FormControl
				v-model="member.doc.member_email"
				type="email"
				:label="__('Email')"
				placeholder="johndoe@example.com"
			/>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import { Dialog, FormControl, useNewDoc } from 'frappe-ui'

import { raiseToast } from '@/utils'

const show = defineModel<boolean>()

const { list } = defineProps<{ list: string }>()

const emit = defineEmits(['reloadMembers'])

const member = useNewDoc(
	'Mailing List External Member',
	{ member_email: '' },
	{
		beforeSubmit: () => (member.doc.mailing_list = list),
		onSuccess: () => {
			show.value = false
			raiseToast(__('Member added.'))
			emit('reloadMembers')
		},
		onError: (error) => raiseToast(error.message, 'error'),
	},
)

watch(show, (val) => {
	if (val) member.doc.member_email = ''
})
</script>
