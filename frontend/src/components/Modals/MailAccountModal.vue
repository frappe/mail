<template>
	<Dialog
		v-if="account?.doc"
		v-model="show"
		:options="{
			title: accountID,
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled:
						(JSON.stringify(account.doc) === JSON.stringify(account.originalDoc) &&
							diskQuota == account.doc.disk_quota) ||
						account.save.loading ||
						account.setQuota.loading,
					onClick: save,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<Switch v-model="account.doc.enabled" :label="__('Enabled')" class="switch" />
				<Switch
					v-model="account.doc.create_mail_contact"
					:label="__('Create Mail Contact')"
					class="switch"
				/>
				<AutocompleteControl
					v-model="account.doc.default_outgoing_email"
					:label="__('Default Email')"
					:show-search="false"
					:options="userAddresses.data"
				/>
				<FormControl v-model="account.doc.display_name" :label="__('Display Name')" />
				<FormControl v-model="account.doc.reply_to" :label="__('Reply To')" />
				<hr />
				<div class="flex flex-col space-y-2">
					<FormControl
						:value="`${account.doc.used_quota.toFixed(2)} GB`"
						:label="__('Used Quota')"
						:readonly="true"
					/>
					<span v-if="account.doc.disk_quota" class="text-ink-gray-5 text-xs">
						{{
							__('{0}% of {1} GB used', [
								account.doc.quota_usage.toFixed(2),
								account.doc.disk_quota,
							])
						}}
					</span>
				</div>
				<Switch
					v-model="setQuota"
					:label="__('Set Quota Restriction')"
					class="switch"
					@update:model-value="diskQuota = $event ? 5 : 0"
				/>
				<template v-if="setQuota">
					<FormControl
						v-model="diskQuota"
						type="number"
						:label="__('Alloted Quota (in GB)')"
					/>
				</template>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, FormControl, Switch, createDocumentResource, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import AutocompleteControl from '@/components/Controls/AutocompleteControl.vue'

import type { MailAccount } from '@/types'

const show = defineModel<boolean>()
const { accountID } = defineProps<{ accountID: string }>()

const account = ref()
const setQuota = ref(false)
const diskQuota = ref(0)

const getAccount = () =>
	createDocumentResource({
		doctype: 'Mail Account',
		name: accountID,
		transform: (data: MailAccount) => {
			for (const d of ['enabled', 'create_mail_contact']) data[d] = !!data[d]
		},
		onSuccess: (data: MailAccount) => {
			setQuota.value = !!data.disk_quota
			diskQuota.value = data.disk_quota || 0
		},
		setValue: {
			onSuccess: () => {
				show.value = false
				raiseToast(__('Account settings saved successfully'))
			},
			onError: (error) => {
				raiseToast(error.messages[0], 'error')
				account.value.reload()
			},
		},
		whitelistedMethods: {
			setQuota: {
				method: 'set_quota',
				makeParams: () => ({
					quota: Math.round(diskQuota.value * 1024 * 1024 * 1024),
				}),
				onSuccess: () => {
					show.value = false
					raiseToast(
						__('Updated quota is being processed. It may take some time to reflect.'),
					)
				},
				onError: (error) => raiseToast(error.messages[0], 'error'),
			},
		},
	})

const save = () => {
	if (diskQuota.value != account.value.doc.disk_quota) account.value.setQuota.submit()
	if (JSON.stringify(account.value.doc) !== JSON.stringify(account.value.originalDoc))
		account.value.save.submit()
}

const userAddresses = createResource({
	url: 'mail.api.admin.get_user_addresses',
	makeParams: () => ({ user: accountID }),
})

watch(
	show,
	(val) => {
		if (!val) return
		account.value = getAccount()
		userAddresses.reload()
	},
	{ immediate: true },
)
</script>

<style>
.switch {
	@apply hover:bg-surface-white active:bg-surface-white cursor-auto !p-0;
}
</style>
