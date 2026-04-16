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
								v-model="automationRules.emails_from"
								:label="__('Emails From')"
								placeholder="john@example.com, jane@example.com, dory@example.io"
								:description="
									__(
										'Emails from these addresses will be automatically moved to this folder.',
									)
								"
							/>
							<FormControl
								v-model="automationRules.subject_contains"
								:label="__('Subject Contains')"
								placeholder="Important, Urgent, Follow Up"
								:description="
									__(
										'Emails with these keywords in the subject will be automatically moved to this folder.',
									)
								"
							/>
							<FormControl
								v-if="
									automationRules.emails_from && automationRules.subject_contains
								"
								v-model="automationRules.match_if"
								:label="__('Match If')"
								type="select"
								:options="[
									{ label: __('Either condition is met'), value: 'any' },
									{ label: __('Both conditions are met'), value: 'all' },
								]"
							/>
							<template
								v-if="
									automationRules.emails_from || automationRules.subject_contains
								"
							>
								<hr />
								<Switch
									v-model="automationRules.mark_as_read"
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
									v-model="automationRules.add_star"
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

const { mailboxes, automationSieve } = userStore()

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
		automation_rules: isDefaultAutomation.value ? null : automationRules,
	}),
	onSuccess: () => {
		raiseToast(__('Folder created.'))
		show.value = false
		mailboxes.reload()
		automationSieve.reload()
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

const updateFolder = createResource({
	url: 'mail.api.mail.update_mailbox',
	makeParams: () => ({
		...folder,
		old_name: original.name,
		automation_rules: isDefaultAutomation.value ? null : automationRules,
	}),
	onSuccess: () => {
		raiseToast(__('Folder updated.'))
		show.value = false
		mailboxes.reload()
		automationSieve.reload()
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

watch(show, (val) => {
	if (!val) return

	tab.value = 0

	if (parsedAutomationRules.value) Object.assign(automationRules, parsedAutomationRules.value)
	else Object.assign(automationRules, DEFAULT_AUTOMATION_RULES)
	if (isNew.value) {
		Object.assign(folder, DEFAULT_FOLDER)
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

const DEFAULT_AUTOMATION_RULES = {
	emails_from: '',
	subject_contains: '',
	mark_as_read: false,
	add_star: false,
	match_if: 'any',
}

const automationRules = reactive({ ...DEFAULT_AUTOMATION_RULES })

const parsedAutomationRules = computed(() => {
	if (isNew.value || !automationSieve.data || !original.name) {
		return null
	}

	const script = automationSieve.data
	// Find the block for this mailbox
	const commentPattern = `# Mailbox: ${original.name}`
	const commentIndex = script.indexOf(commentPattern)

	if (commentIndex === -1) {
		return null
	}

	// Extract the block (from comment to closing brace)
	const blockStart = commentIndex
	const blockEnd = script.indexOf('\n}', blockStart)

	if (blockEnd === -1) {
		return null
	}

	const block = script.substring(blockStart, blockEnd + 2)

	const rules = { ...DEFAULT_AUTOMATION_RULES }

	// Parse emails_from
	const emailsMatch = block.match(/address :is "from" \[(.*?)\]/)
	if (emailsMatch) {
		rules.emails_from = emailsMatch[1]
			.split(',')
			.map((email: string) => email.trim().replace(/"/g, ''))
			.join(', ')
	}

	// Parse subject_contains
	const subjectMatch = block.match(/header :contains "subject" \[(.*?)\]/)
	if (subjectMatch) {
		rules.subject_contains = subjectMatch[1]
			.split(',')
			.map((keyword: string) => keyword.trim().replace(/"/g, ''))
			.join(', ')
	}

	// Parse match_if (anyof vs allof)
	if (block.includes('allof')) {
		rules.match_if = 'all'
	} else if (block.includes('anyof')) {
		rules.match_if = 'any'
	}

	// Parse flags
	rules.mark_as_read = block.includes('setflag "\\\\Seen"')
	rules.add_star = block.includes('setflag "\\\\Flagged"')

	return rules
})

const isDefaultAutomation = computed(
	() => JSON.stringify(automationRules) === JSON.stringify(DEFAULT_AUTOMATION_RULES),
)
</script>
