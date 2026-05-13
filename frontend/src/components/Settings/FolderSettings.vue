<template>
	<div class="flex items-center justify-between">
		<h1>{{ __('Folders') }}</h1>
		<Button icon-left="plus" :label="__('New')" @click="editMailbox()" />
	</div>
	<div v-if="mailboxes?.data?.length">
		<div
			v-for="mailbox in mailboxes?.data"
			:key="mailbox.name"
			class="hover:bg-surface-gray-1 -mx-2 flex cursor-pointer items-center justify-between rounded px-3 py-1"
			@click="editMailbox(mailbox)"
		>
			<div class="flex items-center gap-2">
				<Icon
					:name="getIcon(mailbox)"
					class="stroke-1.5 h-4 w-4 shrink-0"
					:class="FOLDER_ICON_COLOR_MAP[mailbox.color]"
				/>
				<span class="text-base">{{ mailbox._name }}</span>
			</div>
			<div class="flex items-center gap-3">
				<EyeOff v-if="!mailbox.subscribed" class="text-ink-gray-5 h-4 w-4" />
				<Dropdown :options="mailboxOptions(mailbox)">
					<Button variant="" @click.stop>
						<template #icon>
							<Ellipsis class="text-ink-gray-5 h-4 w-4" />
						</template>
					</Button>
				</Dropdown>
			</div>
		</div>
	</div>

	<div v-else class="text-ink-gray-6 flex flex-col space-y-2 text-sm">
		<p class="text-base font-medium">{{ __('No folders found.') }}</p>

		<p>
			{{ __('Folders let you organize your emails into different categories.') }}
		</p>
	</div>

	<FolderModal v-model="showFolderModal" :mailbox="selectedMailbox" />
	<DeleteFolderModal v-model="showDeleteFolderModal" :mailbox="selectedMailbox" />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from 'frappe-ui/icons'
import { Ellipsis, Eye, EyeOff, Settings, Trash2 } from 'lucide-vue-next'
import { Button, Dropdown, createResource } from 'frappe-ui'

import { FOLDER_ICON_COLOR_MAP } from '@/constants'
import { getIcon, raiseToast } from '@/utils'
import { userStore } from '@/stores/user'
import DeleteFolderModal from '@/components/Modals/DeleteFolderModal.vue'
import FolderModal from '@/components/Modals/FolderModal.vue'

import type { MailboxData } from '@/types'

const { mailboxes } = userStore()

const showFolderModal = ref(false)
const selectedMailbox = ref<MailboxData>()
const showDeleteFolderModal = ref(false)

const editMailbox = (mailbox?: MailboxData) => {
	selectedMailbox.value = mailbox
	showFolderModal.value = true
}

const mailboxOptions = (mailbox: MailboxData) => [
	{
		label: mailbox.subscribed ? __('Hide') : __('Show'),
		icon: mailbox.subscribed ? EyeOff : Eye,
		onClick: () =>
			updateFolder.submit({ name: mailbox.name, value: mailbox.subscribed ? 0 : 1 }),
	},
	{
		label: __('Configure'),
		icon: Settings,
		onClick: () => editMailbox(mailbox),
	},
	{
		label: __('Delete'),
		icon: Trash2,
		theme: 'red',
		onClick: () => {
			selectedMailbox.value = mailbox
			showDeleteFolderModal.value = true
		},
	},
]

const updateFolder = createResource({
	url: 'frappe.client.set_value',
	makeParams: ({ name, value }: { name: string; value: 0 | 1 }) => ({
		doctype: 'Mailbox',
		name,
		fieldname: 'subscribed',
		value,
	}),
	onSuccess: () => {
		raiseToast(__('Folder updated.'))
		mailboxes.reload()
	},
	onError: (error) => raiseToast(error.message, 'error'),
})
</script>
