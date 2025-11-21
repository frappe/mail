<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Delete Folder'),
			message: __(
				`Are you sure you want to delete '{0}'? Mails in this folder will be permanently removed.`,
				[mailboxName],
			),
			icon: { name: 'alert-triangle', appearance: 'warning' },
			actions: [{ label: __('Confirm'), variant: 'solid', onClick: deleteFolder.submit }],
		}"
	/>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { Dialog, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

const show = defineModel<boolean>()

const { selectedMailbox } = defineProps<{ selectedMailbox: string }>()

const user = inject('$user')
const { mailboxes } = userStore()

const mailboxName = computed(() => mailboxes.data?.find((m) => m.id === selectedMailbox)?._name)

const deleteFolder = createResource({
	url: 'mail.client.doctype.mailbox.mailbox.delete_mailbox',
	makeParams: () => ({ account: user.data.name, id: selectedMailbox }),
	onSuccess: () => {
		raiseToast(__('Folder deleted successfully'))
		show.value = false
		mailboxes.reload()
	},
	onError: (error) => raiseToast(error.message, 'error'),
})
</script>
