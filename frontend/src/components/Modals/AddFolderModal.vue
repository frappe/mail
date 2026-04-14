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
import { reactive, watch } from 'vue'
import { IconPicker } from 'frappe-ui/icons'
import { Dialog, FormControl, Switch, createResource } from 'frappe-ui'

import { FOLDER_COLOR_MAP } from '@/constants'
import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

const show = defineModel<boolean>()

const { mailboxes } = userStore()

// const parentFolderOptions = computed(() =>
// 	mailboxes.data.map((mailbox) => ({ label: mailbox._name, value: mailbox.id })),
// )

const defaultFolder = {
	name: '',
	parent: null,
	icon: 'folder',
	color: 'Gray',
	disable_push_notification: false,
}

const folder = reactive({ ...defaultFolder })

const createFolder = createResource({
	url: 'mail.api.mail.create_mailbox',
	makeParams: () => folder,
	onSuccess: () => {
		raiseToast(__('Folder created.'))
		show.value = false
		mailboxes.reload()
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

watch(show, (val) => {
	if (val) Object.assign(folder, defaultFolder)
})

const COLOR_OPTIONS = [
	{ label: __('Gray'), value: 'Gray' },
	{ label: __('Blue'), value: 'Blue' },
	{ label: __('Green'), value: 'Green' },
	{ label: __('Amber'), value: 'Amber' },
	{ label: __('Red'), value: 'Red' },
]
</script>
