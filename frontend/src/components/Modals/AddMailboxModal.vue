<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('New Folder'),
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled: !folder.name,
					onClick: createFolder.submit,
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

const show = defineModel<boolean>()

const user = inject('$user')
const { mailboxes } = userStore()

// const parentFolderOptions = computed(() =>
// 	mailboxes.data.map((mailbox) => ({ label: mailbox._name, value: mailbox.id })),
// )

const defaultFolder = {
	account: user.data.name,
	name: '',
	parent: '',
}

const folder = reactive({ ...defaultFolder })

const createFolder = createResource({
	url: 'mail.client.doctype.mailbox.mailbox.add_mailbox',
	makeParams: () => folder,
	onSuccess: () => {
		raiseToast(__('Folder created successfully'))
		show.value = false
		mailboxes.reload()
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

watch(show, (val) => {
	if (val) Object.assign(folder, defaultFolder)
})
</script>
