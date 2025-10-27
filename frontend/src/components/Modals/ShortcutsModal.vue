<template>
	<Dialog :options="{ title: __('Shortcuts'), size: '4xl' }">
		<template #body-content>
			<div class="grid w-full grid-cols-2 gap-10 py-1">
				<div v-for="group in shortcutGroups" :key="group.title" class="pb-4">
					<h2 class="text-ink-gray-8 mb-4 text-lg font-semibold">{{ group.title }}</h2>
					<ul class="space-y-2">
						<li
							v-for="(shortcut, index) in group.shortcuts"
							:key="index"
							class="flex items-start justify-between"
						>
							<div class="text-ink-gray-7 text-base">{{ shortcut[1] }}</div>
							<div class="flex w-[9rem] justify-start gap-1 space-x-1">
								<span
									v-for="(key, kIndex) in shortcut[0]"
									:key="kIndex"
									class="text-ink-gray-8 my-auto text-xs"
									:class="{
										'bg-surface-gray-2 border-outline-gray-2 rounded-sm border px-2 py-0.5 font-mono shadow-sm':
											key !== 'or',
									}"
								>
									{{ key }}
								</span>
							</div>
						</li>
					</ul>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { Dialog } from 'frappe-ui'

import { isMac } from '@/utils'
import { type MailboxRole, userStore } from '@/stores/user'

const { mailboxes } = userStore()

const mailboxName = (role: MailboxRole) => mailboxes.data?.find((m) => m.role === role)._name

const modifier = computed(() => (isMac ? '⌘' : 'Ctrl'))

const shortcutGroups = computed(() => [
	{
		title: __('Compose'),
		shortcuts: [
			[['C'], __('Compose New Mail')],
			[[modifier.value, 'Enter'], __('Send Mail')],
			[[modifier.value, 'D'], __('Discard Draft')],
			[['R'], __('Reply to Mail')],
			[['Shift', 'R'], __('Reply All to Mail')],
			[['F'], __('Forward Mail')],
		],
	},
	{
		title: __('Navigation'),
		shortcuts: [
			[['↓', 'or', 'J'], __('Go to Next Mail')],
			[['↑', 'or', 'K'], __('Go to Previous Mail')],
			[['G', 'I'], __('Go to {0}', [mailboxName('inbox')])],
			[['G', 'S'], __('Go to {0}', [mailboxName('sent')])],
			[['G', 'D'], __('Go to {0}', [mailboxName('drafts')])],
			[[modifier.value, 'K'], __('Search Mail')],
		],
	},
	{
		title: __('Actions'),
		shortcuts: [
			[[modifier.value, 'A'], __('Select All Mails')],
			[['Esc'], __('Clear All Mails')],
			[['!'], __('Mark as Junk')],
			[['U'], __('Mark as Unread')],
			[['Shift', 'U'], __('Mark as Read')],
			[['Delete'], __('Move to Trash')],
			[['Shift', 'Delete'], __('Permanently Delete Mail')],
		],
	},
	{
		title: __('Other'),
		shortcuts: [
			[[modifier.value, ','], __('Open Settings')],
			[[modifier.value, ';'], __('Toggle Sidebar')],
			[['?'], __('View Shortcuts')],
		],
	},
])
</script>
