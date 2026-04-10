<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Edit Folder'),
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled: !folder.name,
					onClick: updateFolder.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="folder.name" :label="__('Folder Name')" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { inject, reactive, watch } from 'vue'
import { Dialog, FormControl, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

import type { MailboxData } from '@/types'

const show = defineModel<boolean>()

const { mailbox } = defineProps<{ mailbox?: MailboxData }>()

const user = inject('$user')
const { mailboxes } = userStore()

// const parentFolderOptions = computed(() =>
// 	mailboxes.data.map((mailbox) => ({ label: mailbox._name, value: mailbox.id })),
// )

const folder = reactive({
	user: user.data.name,
	id: '',
	name: '',
	role: null,
	parent: null,
})

const updateFolder = createResource({
	url: 'mail.client.doctype.mailbox.mailbox.update_mailbox',
	makeParams: () => folder,
	onSuccess: () => {
		raiseToast(__('Folder updated.'))
		show.value = false
		mailboxes.reload()
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

watch(show, (val) => {
	if (!val || !mailbox) return
	folder.id = mailbox.id
	folder.name = mailbox._name
	folder.role = mailbox.role
})
</script>
