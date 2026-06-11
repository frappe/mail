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
					disabled: !isEditableInvite || !accountRequest.isDirty,
					onClick: saveInvite,
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
					v-model="inviteRole"
					type="select"
					:label="__('Role')"
					:options="ROLE_OPTIONS"
					:disabled="!isEditableInvite"
				/>
				<FormControl
					:label="__('Backup Email')"
					:value="accountRequest.doc.backup_email"
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
					:disabled="!isEditableInvite"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Dialog, FormControl, createDocumentResource } from 'frappe-ui'

import { raiseToast } from '@/utils'

const show = defineModel<boolean>()

const { inviteID } = defineProps<{ inviteID: string }>()

const emit = defineEmits(['reloadInvites'])

type InviteDoc = {
	account: string
	is_admin: boolean | 0 | 1
	backup_email: string
	invited_by: string
	expires_at?: string
	is_verified: boolean | 0 | 1
}

type AccountRequestResource = {
	doc?: InviteDoc
	isDirty: boolean
	save?: { submit?: () => void }
	reload?: () => void
}

const accountRequest = ref<AccountRequestResource>()

const ROLE_OPTIONS = [
	{ label: __('User'), value: 'user' },
	{ label: __('Admin'), value: 'admin' },
]

const inviteRole = computed<'user' | 'admin'>({
	get: () => (accountRequest.value?.doc?.is_admin ? 'admin' : 'user'),
	set: (value) => {
		if (!accountRequest.value?.doc) return
		accountRequest.value.doc.is_admin = value === 'admin'
	},
})

const isEditableInvite = computed(() => {
	const doc = accountRequest.value?.doc
	if (!doc) return false
	return !doc.is_verified
})

const saveInvite = () => {
	if (!isEditableInvite.value) return
	accountRequest.value?.save?.submit?.()
}

const getMailAccountRequest = () =>
	createDocumentResource({
		doctype: 'Mail Account Request',
		name: inviteID,
		setValue: {
			onSuccess: () => {
				show.value = false
				raiseToast(__('Invite updated.'))
				emit('reloadInvites')
			},
			onError: (error: { messages?: string[] }) => {
				raiseToast(error.messages?.[0] || __('Failed to update invite.'), 'error')
				accountRequest.value?.reload?.()
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
