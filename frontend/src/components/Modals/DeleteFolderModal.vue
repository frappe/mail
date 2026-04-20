<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Delete Folder'),
			message: __(
				`Are you sure you want to delete '{0}'? Mails in this folder will be permanently removed.`,
				[mailbox?._name],
			),
			icon: { name: 'alert-triangle', appearance: 'warning' },
			actions: [{ label: __('Confirm'), variant: 'solid', onClick: deleteFolder.submit }],
		}"
	/>
</template>

<script setup lang="ts">
import { Dialog, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

import type { MailboxData } from '@/types'

const show = defineModel<boolean>()

const { mailbox } = defineProps<{ mailbox?: MailboxData }>()

const { mailboxes, sieveScripts } = userStore()

const deleteFolder = createResource({
	url: 'mail.api.mail.delete_mailbox',
	makeParams: () => ({ id: mailbox.id, name: mailbox._name }),
	onSuccess: () => {
		raiseToast(__('Folder deleted.'))
		show.value = false
		mailboxes.reload()
		sieveScripts.reload()
	},
	onError: (error) => raiseToast(error.message, 'error'),
})
</script>
