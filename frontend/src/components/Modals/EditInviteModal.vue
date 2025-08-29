<template>
	<Dialog
		v-if="accountRequest?.doc"
		v-model="show"
		:options="{
			title: __('Edit Invite'),
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled: !accountRequest.isDirty,
					onClick: accountRequest.save.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					:label="__('Assigned Email')"
					:value="accountRequest.doc.account"
					disabled
				/>
				<FormControl
					:label="__('Assigned Role')"
					:value="accountRequest.doc.is_admin ? __('Mail Admin') : __('Mail User')"
					disabled
				/>
				<FormControl
					:label="__('Backup Email')"
					:value="accountRequest.doc.email"
					disabled
				/>
				<FormControl
					:label="__('Invited By')"
					:value="accountRequest.doc.invited_by"
					disabled
				/>
				<FormControl
					v-model="accountRequest.doc.expires_at"
					type="datetime-local"
					:label="__('Expires At')"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, FormControl, createDocumentResource } from 'frappe-ui'

import { raiseToast } from '@/utils'

const show = defineModel<boolean>()

const { inviteID } = defineProps<{ inviteID: string }>()

const emit = defineEmits(['reloadInvites'])

const accountRequest = ref()

const getMailAccountRequest = () =>
	createDocumentResource({
		doctype: 'Mail Account Request',
		name: inviteID,
		setValue: {
			onSuccess: () => {
				show.value = false
				raiseToast(__('Invite updated successfully'))
				emit('reloadInvites')
			},
			onError: (error) => {
				raiseToast(error.messages[0], 'error')
				accountRequest.value.reload()
			},
		},
	})

watch(
	show,
	(val) => {
		if (val) accountRequest.value = getMailAccountRequest()
	},
	{ immediate: true },
)
</script>
