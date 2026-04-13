<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Folder Settings'),
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
				<FormControl v-model="folder.name" :label="__('Name')" />

				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Icon') }}</label>
					<IconPicker v-model="folder.icon" />
				</div>

				<FormControl
					v-model="folder.color"
					type="select"
					:label="__('Color')"
					:options="COLOR_OPTIONS"
				>
					<template #prefix>
						<span class="h-4 w-4 shrink-0 rounded-full" :class="folder.color" />
					</template>
				</FormControl>

				<hr />
				<Switch
					v-model="folder.disable_push_notification"
					:label="__('Disable Push Notifications')"
					:description="__('Check to disable push notifications for this folder.')"
					class="!p-0"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { inject, reactive, watch } from 'vue'
import { IconPicker } from 'frappe-ui/icons'
import { Dialog, FormControl, Select, Switch, createResource } from 'frappe-ui'

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
	icon: 'folder',
	color: 'bg-surface-gray-6',
	disable_push_notification: false,
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
	if (mailbox.icon) folder.icon = mailbox.icon
	if (mailbox.color) folder.color = mailbox.color
	if (mailbox.disable_push_notification)
		folder.disable_push_notification = !!mailbox.disable_push_notification
})

const COLOR_OPTIONS = [
	{ label: __('Gray'), value: 'bg-surface-gray-6' },
	{ label: __('Blue'), value: 'bg-surface-blue-3' },
	{ label: __('Green'), value: 'bg-surface-green-3' },
	{ label: __('Amber'), value: 'bg-surface-amber-3' },
	{ label: __('Red'), value: 'bg-surface-red-5' },
]
</script>
