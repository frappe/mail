<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Folder Settings'),
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled: !folder.name || isNotDirty,
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
						<span
							class="h-4 w-4 shrink-0 rounded-full"
							:class="FOLDER_COLOR_MAP[folder.color]"
						/>
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
import { computed, reactive, watch } from 'vue'
import { IconPicker } from 'frappe-ui/icons'
import { Dialog, FormControl, Switch, createResource } from 'frappe-ui'

import { FOLDER_COLOR_MAP } from '@/constants'
import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

import type { MailboxData } from '@/types'

const show = defineModel<boolean>()

const { mailbox } = defineProps<{ mailbox?: MailboxData }>()

const { mailboxes } = userStore()

// const parentFolderOptions = computed(() =>
// 	mailboxes.data.map((mailbox) => ({ label: mailbox._name, value: mailbox.id })),
// )

const folder = reactive({
	id: '',
	name: '',
	role: null,
	parent: null,
	icon: 'folder',
	color: 'Gray',
	disable_push_notification: false,
})

const original = reactive({
	id: '',
	name: '',
	role: null,
	parent: null,
	icon: 'folder',
	color: 'Gray',
	disable_push_notification: false,
})

const isNotDirty = computed(
	() =>
		folder.name === original.name &&
		folder.icon === original.icon &&
		folder.color === original.color &&
		folder.disable_push_notification === original.disable_push_notification,
)

const updateFolder = createResource({
	url: 'mail.api.mail.update_mailbox',
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
	folder.id = original.id = mailbox.id
	folder.name = original.name = mailbox._name
	folder.role = original.role = mailbox.role
	folder.icon = original.icon = mailbox.icon || 'folder'
	folder.color = original.color = mailbox.color || 'Gray'
	folder.disable_push_notification = original.disable_push_notification =
		!!mailbox.disable_push_notification
})

const COLOR_OPTIONS = [
	{ label: __('Gray'), value: 'Gray' },
	{ label: __('Blue'), value: 'Blue' },
	{ label: __('Green'), value: 'Green' },
	{ label: __('Amber'), value: 'Amber' },
	{ label: __('Red'), value: 'Red' },
]
</script>
