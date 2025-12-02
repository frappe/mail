<template>
	<Dialog :options="{ title: __('Shortcuts'), size: '5xl' }">
		<template #body-content>
			<div class="grid max-h-[75vh] w-full grid-cols-2 gap-10 overflow-y-auto py-1">
				<div v-for="(column, index) in shortcutGroups" :key="index">
					<div v-for="group in column" :key="group.title" class="pb-8">
						<h2 class="text-ink-gray-8 mb-4 text-lg font-semibold">
							{{ group.title }}
						</h2>
						<ul class="space-y-2">
							<li
								v-for="(shortcut, sIndex) in group.shortcuts"
								:key="sIndex"
								class="flex items-start justify-between"
							>
								<div class="text-ink-gray-7 text-base">{{ shortcut[1] }}</div>
								<div class="flex w-[14rem] justify-start gap-1 space-x-1">
									<span
										v-for="(key, kIndex) in shortcut[0]"
										:key="kIndex"
										class="text-ink-gray-8 my-auto text-xs"
										:class="{
											'bg-surface-gray-2 border-outline-gray-2 rounded-sm border px-2 py-0.5 font-mono shadow-sm':
												![__('or'), __('then')].includes(key),
										}"
									>
										{{ key }}
									</span>
								</div>
							</li>
						</ul>
					</div>
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

const mailboxName = (role: MailboxRole) => mailboxes.data?.find((m) => m.role === role)?._name

const modifier = computed(() => (isMac ? '⌘' : 'Ctrl'))

const shortcutGroups = computed(() => [
	[
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
			title: __('Actions'),
			shortcuts: [
				[[modifier.value, 'A'], __('Select All Mails')],
				[['Esc'], __('Clear All Mails')],
				[['Shift', '↓', __('or'), 'Shift', 'J'], __('Toggle Select Downwards')],
				[['Shift', '↑', __('or'), 'Shift', 'K'], __('Toggle Select Upwards')],
				[['!'], __('Mark as Junk')],
				[['U'], __('Mark as Unread')],
				[['Shift', 'U'], __('Mark as Read')],
				[['Delete'], __('Move to Trash')],
				[['Shift', 'Delete'], __('Permanently Delete')],
				[[modifier.value, 'Z'], __('Undo Last Action')],
			],
		},
	],
	[
		{
			title: __('Navigation'),
			shortcuts: [
				[['↓', __('or'), 'J'], __('Go to Next Mail')],
				[['↑', __('or'), 'K'], __('Go to Previous Mail')],
				[['G', __('then'), 'G'], __('Go to First Mail')],
				[['Shift', 'G'], __('Go to Last Mail')],
				[['Enter'], __('Open Mail')],
				[[modifier.value, 'K'], __('Search Mail')],
				[['G', __('then'), 'I'], __('Go to {0}', [mailboxName('inbox')])],
				[['G', __('then'), 'F'], __('Go to Starred')],
				[['G', __('then'), 'S'], __('Go to {0}', [mailboxName('sent')])],
				[['G', __('then'), 'D'], __('Go to {0}', [mailboxName('drafts')])],
				[['G', __('then'), 'J'], __('Go to {0}', [mailboxName('junk')])],
				[['G', __('then'), 'T'], __('Go to {0}', [mailboxName('trash')])],
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
	],
])
</script>
