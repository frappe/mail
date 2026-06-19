<template>
	<Dialog v-model="showBlockSender" :options="options">
		<template v-if="isMultiple" #body-content>
			<div class="border-outline-gray-2 overflow-hidden rounded-md border">
				<!-- Select all -->
				<div
					class="bg-surface-gray-1 flex cursor-pointer items-center gap-3 px-3.5 py-2.5"
					@click="toggleAll"
				>
					<FormControl
						type="checkbox"
						:model-value="allSelected"
						class="pointer-events-none"
						size="md"
					/>
					<span class="text-ink-gray-7 text-sm font-medium">
						{{ allSelected ? __('Deselect all') : __('Select all') }}
					</span>
					<span class="text-ink-gray-5 ml-auto text-sm">
						{{ __('{0} of {1} selected', [selectedCount, sendersToBlock.length]) }}
					</span>
				</div>

				<!-- Sender list -->
				<div
					class="divide-outline-gray-2 border-outline-gray-2 max-h-[290px] divide-y overflow-y-auto border-t"
				>
					<div
						v-for="sender in sendersToBlock"
						:key="sender.email"
						class="hover:bg-surface-gray-1 flex cursor-pointer items-center gap-3 px-3.5 py-2.5 transition-colors"
						@click="toggle(sender.email)"
					>
						<FormControl
							type="checkbox"
							:model-value="selected[sender.email]"
							class="pointer-events-none"
							size="md"
						/>
						<div class="min-w-0 flex-1 space-y-0.5">
							<div class="text-ink-gray-8 truncate text-sm font-medium">
								{{ sender.name || sender.email }}
							</div>
							<div v-if="sender.name" class="text-ink-gray-5 truncate text-xs">
								{{ sender.email }}
							</div>
						</div>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Dialog, FormControl, createResource } from 'frappe-ui'

import { raisePromiseToast } from '@/utils'
import { useBlockSender, useUndo } from '@/utils/composables'
import { userStore } from '@/stores/user'

const store = userStore()
const { blockedAddresses } = store
const { showBlockSender, sendersToBlock } = useBlockSender()
const { setUndoAction } = useUndo()

const isMultiple = computed(() => sendersToBlock.value.length > 1)

// Which senders are checked (multi-select only). Reset to all-selected each time the prompt opens.
const selected = reactive<Record<string, boolean>>({})
watch(showBlockSender, (open) => {
	if (!open) return
	Object.keys(selected).forEach((key) => delete selected[key])
	sendersToBlock.value.forEach((sender) => (selected[sender.email] = true))
})

const selectedCount = computed(
	() => sendersToBlock.value.filter((sender) => selected[sender.email]).length,
)
const allSelected = computed(
	() => sendersToBlock.value.length > 0 && selectedCount.value === sendersToBlock.value.length,
)
const toggle = (email: string) => (selected[email] = !selected[email])
const toggleAll = () => {
	const next = !allSelected.value
	sendersToBlock.value.forEach((sender) => (selected[sender.email] = next))
}

const blockEmailAddresses = createResource({
	url: 'mail.api.mail.block_email_addresses',
	makeParams: ({ emails }: { emails: string[] }) => ({ account: store.account, emails }),
	onSuccess: () => blockedAddresses.reload(),
})

const handleBlock = () => {
	const emails = (
		isMultiple.value
			? sendersToBlock.value.filter((sender) => selected[sender.email])
			: sendersToBlock.value
	).map((sender) => sender.email)
	showBlockSender.value = false
	if (!emails.length) return

	// Blocking supersedes the junk action's undo — clear it so a following Ctrl+Z is a no-op (the
	// junk toast's own Undo button is dismissed by raisePromiseToast's toast.removeAll()).
	setUndoAction(undefined)

	const action = () => blockEmailAddresses.submit({ emails })
	const success = emails.length === 1 ? __('Sender blocked.') : __('Senders blocked.')
	raisePromiseToast(action, __('Blocking...'), success)
}

const options = computed(() => {
	const count = isMultiple.value ? selectedCount.value : 1
	return {
		title: __('Block {0}?', [count === 1 ? __('sender') : __('senders')]),
		message: isMultiple.value
			? __("You won't receive future messages from the selected senders.")
			: __("You won't receive future messages from {0}.", [sendersToBlock.value[0]?.email]),
		actions: [
			{
				label: __('Cancel'),
				onClick: () => (showBlockSender.value = false),
			},
			{
				label: __('Block'),
				variant: 'solid',
				autofocus: true,
				disabled: isMultiple.value && count === 0,
				onClick: handleBlock,
			},
		],
	}
})
</script>
