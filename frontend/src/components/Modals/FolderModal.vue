<template>
	<Dialog
		v-model="show"
		:options="{
			title: isNew ? __('New Folder') : __('Folder Settings'),
			size: 'xl',
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled: !folder.name || (!isNew && isNotDirty),
					onClick: () => (isNew ? createFolder.submit() : updateFolder.submit()),
				},
			],
		}"
	>
		<template #body-content>
			<Tabs v-model="tab" :tabs="TABS">
				<template #tab-panel>
					<div class="h-96 shrink-0 space-y-4 pt-4 sm:pt-6">
						<!-- General -->
						<template v-if="tab === 0">
							<FormControl v-model="folder.name" :label="__('Name')" required />
							<div class="space-y-1.5">
								<label class="text-ink-gray-5 block text-xs">{{
									__('Icon')
								}}</label>
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
								:disabled="isNotificationsDisabled"
								:description="
									__('Check to disable push notifications for this folder.')
								"
								class="!p-0"
							/>
						</template>

						<!-- Automation  -->
						<template v-else>
							<FormControl
								v-model="automation.emails_from"
								:label="__('Emails From')"
								placeholder="john@example.com, jane@example.com, dory@example.io"
								:description="
									__(
										'Emails from these addresses will be automatically moved to this folder.',
									)
								"
							/>
							<FormControl
								v-model="automation.subject_contains"
								:label="__('Subject Contains')"
								placeholder="Important, Urgent, Follow Up"
								:description="
									__(
										'Emails with these keywords in the subject will be automatically moved to this folder.',
									)
								"
							/>
							<FormControl
								v-if="automation.emails_from && automation.subject_contains"
								v-model="automation.match_if"
								:label="__('Match If')"
								type="select"
								:options="[
									{ label: __('Either condition is met'), value: 'any' },
									{ label: __('Both conditions are met'), value: 'all' },
								]"
							/>
							<template v-if="automation.emails_from || automation.subject_contains">
								<hr />
								<Switch
									v-model="automation.mark_as_read"
									:label="__('Mark as Read')"
									:disabled="isNotificationsDisabled"
									:description="
										__(
											'Automatically mark emails as read when they are moved to this folder.',
										)
									"
									class="!p-0"
								/>
								<Switch
									v-model="automation.add_star"
									:label="__('Add Star')"
									:disabled="isNotificationsDisabled"
									:description="
										__(
											'Automatically star emails when they are moved to this folder.',
										)
									"
									class="!p-0"
								/>
							</template>
						</template>
					</div>
				</template>
			</Tabs>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { IconPicker } from 'frappe-ui/icons'
import { Settings, Zap } from 'lucide-vue-next'
import { Dialog, FormControl, Switch, Tabs, createResource } from 'frappe-ui'

import { FOLDER_COLOR_MAP, FOLDER_ICON_MAP } from '@/constants'
import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

import type { MailboxData } from '@/types'

const show = defineModel<boolean>()

const { mailbox } = defineProps<{ mailbox?: MailboxData }>()

const { mailboxes } = userStore()

const isNew = computed(() => !mailbox)

const tab = ref(0)

const TABS = [
	{ label: __('General'), icon: Settings, index: 0 },
	{ label: __('Automation'), icon: Zap, index: 1 },
]

const DEFAULT_FOLDER = {
	id: '',
	name: '',
	role: null,
	parent: null,
	icon: 'folder',
	color: 'Gray',
	disable_push_notification: false,
}

const folder = reactive({ ...DEFAULT_FOLDER })

const original = reactive({ ...DEFAULT_FOLDER })

const isNotificationsDisabled = computed(
	() =>
		!isNew.value &&
		mailbox?.role &&
		['sent', 'drafts', 'junk', 'trash'].includes(mailbox.role),
)

const isNotDirty = computed(
	() =>
		folder.name === original.name &&
		folder.icon === original.icon &&
		folder.color === original.color &&
		folder.disable_push_notification === original.disable_push_notification,
)

const createFolder = createResource({
	url: 'mail.api.mail.create_mailbox',
	makeParams: () => ({
		...folder,
		automation_rules: isDefaultAutomation.value ? null : automation,
	}),
	onSuccess: () => {
		raiseToast(__('Folder created.'))
		show.value = false
		mailboxes.reload()
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

const updateFolder = createResource({
	url: 'mail.api.mail.update_mailbox',
	makeParams: () => ({
		...folder,
		old_name: original.name,
		automation_rules: isDefaultAutomation.value ? null : automation,
	}),
	onSuccess: () => {
		raiseToast(__('Folder updated.'))
		show.value = false
		mailboxes.reload()
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

watch(show, (val) => {
	if (!val) return

	tab.value = 0

	if (isNew.value) {
		Object.assign(folder, DEFAULT_FOLDER)
		Object.assign(automation, DEFAULT_AUTOMATION)
		return
	}

	folder.id = original.id = mailbox.id
	folder.name = original.name = mailbox._name
	folder.role = original.role = mailbox.role
	folder.icon = original.icon = mailbox.icon || FOLDER_ICON_MAP[mailbox.role] || 'folder'
	folder.color = original.color = mailbox.color || 'Gray'
	folder.disable_push_notification = original.disable_push_notification =
		isNotificationsDisabled.value ? true : !!mailbox.disable_push_notification
})

const COLOR_OPTIONS = [
	{ label: __('Gray'), value: 'Gray' },
	{ label: __('Blue'), value: 'Blue' },
	{ label: __('Green'), value: 'Green' },
	{ label: __('Amber'), value: 'Amber' },
	{ label: __('Red'), value: 'Red' },
	{ label: __('Purple'), value: 'Purple' },
]

const DEFAULT_AUTOMATION = {
	emails_from: '',
	subject_contains: '',
	mark_as_read: false,
	add_star: false,
	match_if: 'any',
}

const automation = reactive({ ...DEFAULT_AUTOMATION })

const isDefaultAutomation = computed(
	() => JSON.stringify(automation) === JSON.stringify(DEFAULT_AUTOMATION),
)
</script>
