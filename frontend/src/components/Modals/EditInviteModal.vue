<template>
	<Dialog
		v-if="accountRequest?.doc"
		v-model="show"
		:options="{
			title: __('Edit Invite'),
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled: !accountRequest.isDirty,
					onClick: accountRequest.save.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					:label="__('Assigned Email')"
					:value="accountRequest.doc.account"
					disabled
				/>
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Roles') }}</label>
					<div class="flex flex-wrap gap-1">
						<Badge
							v-for="r in (accountRequest.doc.roles || '').split('\n')"
							:key="r"
							:label="r"
							:theme="
								r === 'admin'
									? 'red'
									: r === 'tenant-admin'
										? 'orange'
										: r === 'user'
											? 'blue'
											: 'gray'
							"
						/>
					</div>
				</div>
				<FormControl
					:label="__('Backup Email')"
					:value="accountRequest.doc.backup_email"
					disabled
				/>
				<FormControl
					:label="__('Invited By')"
					:value="accountRequest.doc.invited_by"
					disabled
				/>
				<FormControl
					v-model="accountRequest.doc.expires_at"
					type="datetime-local"
					:label="__('Expires At')"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Badge, Dialog, FormControl, createDocumentResource } from 'frappe-ui'

import { raiseToast } from '@/utils'

const show = defineModel<boolean>()

const { inviteID } = defineProps<{ inviteID: string }>()

const emit = defineEmits(['reloadInvites'])

const accountRequest = ref()

const getMailAccountRequest = () =>
	createDocumentResource({
		doctype: 'Mail Account Request',
		name: inviteID,
		setValue: {
			onSuccess: () => {
				show.value = false
				raiseToast(__('Invite updated.'))
				emit('reloadInvites')
			},
			onError: (error) => {
				raiseToast(error.messages[0], 'error')
				accountRequest.value.reload()
			},
		},
	})

watch(
	show,
	(val) => {
		if (val) accountRequest.value = getMailAccountRequest()
	},
	{ immediate: true },
)
</script>
