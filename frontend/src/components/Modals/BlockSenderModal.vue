<template>
	<Dialog v-model="showBlockSender" :options="options">
		<template v-if="sendersToBlock.length > 1" #body-content>
			<div class="flex flex-col gap-3">
				<label
					v-for="email in sendersToBlock"
					:key="email"
					class="flex cursor-pointer items-center gap-2"
				>
					<Checkbox v-model="selected[email]" />
					<span class="text-ink-gray-7 truncate text-base">{{ email }}</span>
				</label>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Checkbox, Dialog, createResource } from 'frappe-ui'

import { raisePromiseToast } from '@/utils'
import { useBlockSender, useUndo } from '@/utils/composables'
import { userStore } from '@/stores/user'

const store = userStore()
const { blockedAddresses } = store
const { showBlockSender, sendersToBlock } = useBlockSender()
const { setUndoAction } = useUndo()

// Which of the listed senders are checked (only relevant when there's more than one). Reset to all
// selected each time the prompt opens.
const selected = reactive<Record<string, boolean>>({})
watch(showBlockSender, (open) => {
	if (!open) return
	Object.keys(selected).forEach((key) => delete selected[key])
	sendersToBlock.value.forEach((email) => (selected[email] = true))
})

const blockEmailAddresses = createResource({
	url: 'mail.api.mail.block_email_addresses',
	makeParams: ({ emails }: { emails: string[] }) => ({ account: store.account, emails }),
	onSuccess: () => blockedAddresses.reload(),
})

const handleBlock = () => {
	const emails =
		sendersToBlock.value.length === 1
			? sendersToBlock.value
			: sendersToBlock.value.filter((email) => selected[email])
	showBlockSender.value = false
	if (!emails.length) return

	// Blocking supersedes the junk action's undo — clear it so a following Ctrl+Z is a no-op (the
	// junk toast's own Undo button is dismissed by raisePromiseToast's toast.removeAll()).
	setUndoAction(undefined)

	const action = () => blockEmailAddresses.submit({ emails })
	const success = emails.length === 1 ? __('Sender blocked.') : __('Senders blocked.')
	raisePromiseToast(action, __('Blocking...'), success)
}

const options = computed(() => ({
	title: sendersToBlock.value.length > 1 ? __('Block Senders') : __('Block Sender'),
	message:
		sendersToBlock.value.length === 1
			? __("Block {0}? You won't receive future messages from them.", [
					sendersToBlock.value[0],
				])
			: __(
					"Select the senders you want to block. You won't receive future messages from blocked senders.",
				),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [
		{
			label: __('Block'),
			variant: 'solid',
			autofocus: true,
			onClick: handleBlock,
		},
	],
}))
</script>
