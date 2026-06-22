<template>
	<template v-if="accountSettings.doc">
		<h1>{{ __('Outgoing') }}</h1>
		<FormControl
			v-model="accountSettings.doc.default_outgoing_email"
			type="combobox"
			:label="__('Default Outgoing Email')"
			variant="outline"
			:options="identities.data.map((i: Identity) => i.email)"
			:open-on-click="true"
		/>
		<Switch
			v-model="createContactsAfterEmailSubmit"
			:label="__('Create Contacts After Sending Email')"
			:description="
				__('Automatically creates contacts for new recipients after an email is sent.')
			"
			class="!p-0"
		/>
		<Switch
			v-model="destroyEmailAfterSubmit"
			:label="__('Delete Email After Sending')"
			:description="
				__('Automatically deletes the email from your mailbox after it is sent.')
			"
			class="!p-0"
		/>
		<Switch
			v-model="destroyNewsletterAfterSubmit"
			:label="__('Delete Newsletter After Sending')"
			:description="__('Automatically deletes the newsletter after it is sent.')"
			class="!p-0"
		/>

		<h1>{{ __('Incoming') }}</h1>
		<FormControl
			v-model="accountSettings.doc.on_mark_as_junk"
			type="select"
			:label="__('When Marking as Junk')"
			variant="outline"
			:options="ON_MARK_AS_JUNK_OPTIONS"
		/>

		<template v-if="userSettings.doc">
			<h1>{{ __('Recovery') }}</h1>
			<FormControl
				v-model="userSettings.doc.backup_email"
				:label="__('Backup Email')"
				:description="
					__(`We'll contact you here if there's an issue with your main account.`)
				"
				variant="outline"
			/>
		</template>

		<ErrorMessage :message="accountSettings.save.error || userSettings.save.error" />
		<Button
			:label="__('Save')"
			variant="solid"
			:disabled="loading || !isDirty"
			:loading="saving"
			class="min-h-7"
			@click="save"
		/>
	</template>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { Button, ErrorMessage, FormControl, Switch, createDocumentResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

import type { Identity } from '@/types'

const user = inject('$user')
const { account, identities } = userStore()

// Outgoing settings now live on the active account's Account Settings; backup_email
// (Recovery) is still per-user on User Settings.
const activeAccount = user.data?.accounts?.find((a) => a.name === account)

const accountSettings = createDocumentResource({
	doctype: 'Account Settings',
	name: activeAccount?.account_settings,
})

const userSettings = createDocumentResource({
	doctype: 'User Settings',
	name: user.data?.user_settings,
})

const createContactsAfterEmailSubmit = computed({
	get: () => !!accountSettings.doc.create_contacts_after_email_submit,
	set: (val: boolean) => (accountSettings.doc.create_contacts_after_email_submit = val ? 1 : 0),
})

const destroyEmailAfterSubmit = computed({
	get: () => !!accountSettings.doc.destroy_email_after_submit,
	set: (val: boolean) => (accountSettings.doc.destroy_email_after_submit = val ? 1 : 0),
})

const destroyNewsletterAfterSubmit = computed({
	get: () => !!accountSettings.doc.destroy_newsletter_after_submit,
	set: (val: boolean) => (accountSettings.doc.destroy_newsletter_after_submit = val ? 1 : 0),
})

const ON_MARK_AS_JUNK_OPTIONS = [
	{
		label: __("Move the sender's future mail to Junk automatically"),
		value: "Junk Sender's Mail",
	},
	{ label: __('Ask whether to block the sender'), value: 'Ask to Block Sender' },
]

const accountDirty = computed(
	() => JSON.stringify(accountSettings.doc) !== JSON.stringify(accountSettings.originalDoc),
)
const userDirty = computed(
	() => JSON.stringify(userSettings.doc) !== JSON.stringify(userSettings.originalDoc),
)
const isDirty = computed(() => accountDirty.value || userDirty.value)
const loading = computed(() => accountSettings.get.loading || userSettings.get.loading)
const saving = computed(() => accountSettings.save.loading || userSettings.save.loading)

const save = async () => {
	if (accountDirty.value) {
		await accountSettings.save.submit()
		// Sync the shared user data so compose picks up the new default and the junk flow picks up
		// the "on mark as junk" choice without a page reload (both read from user.data.accounts).
		if (activeAccount) {
			activeAccount.default_outgoing_email = accountSettings.doc.default_outgoing_email
			activeAccount.on_mark_as_junk = accountSettings.doc.on_mark_as_junk
		}
	}
	if (userDirty.value) await userSettings.save.submit()
	raiseToast(__('Account updated.'))
}
</script>
