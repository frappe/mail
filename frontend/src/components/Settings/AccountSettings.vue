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
		<Switch
			v-model="enableScreening"
			:label="__('Screen New Senders')"
			:description="
				__(
					'Emails from new senders go to the Screener instead of your Inbox. Only accepted senders reach your Inbox.',
				)
			"
			class="!p-0"
		/>
		<FormControl
			v-model="accountSettings.doc.on_mark_as_junk"
			type="select"
			:label="__('When Marking as Junk')"
			variant="outline"
			:options="ON_MARK_AS_JUNK_OPTIONS"
		/>
		<Switch
			v-model="blockRemoteImages"
			:label="__('Block Remote Images')"
			:description="__(`Don't load remote images from untrusted sources by default.`)"
			class="!p-0"
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

		<Dialog v-model="showMoveToInbox" :options="moveToInboxOptions" />
	</template>
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import {
	Button,
	Dialog,
	ErrorMessage,
	FormControl,
	Switch,
	createDocumentResource,
	createResource,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

import type { Identity, MailboxData } from '@/types'

const user = inject('$user')
const { account, identities, mailboxes, mailboxIds } = userStore()

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

const enableScreening = computed({
	get: () => !!accountSettings.doc.enable_screening,
	set: (val: boolean) => (accountSettings.doc.enable_screening = val ? 1 : 0),
})

const blockRemoteImages = computed({
	get: () => !!accountSettings.doc.block_remote_images,
	set: (val: boolean) => (accountSettings.doc.block_remote_images = val ? 1 : 0),
})

const ON_MARK_AS_JUNK_OPTIONS = [
	{
		label: __("Move the sender's future emails to Junk automatically"),
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

const showMoveToInbox = ref(false)

const moveScreeningToInbox = createResource({
	url: 'mail.api.mail.move_screening_mails_to_inbox',
	makeParams: () => ({ account }),
	onSuccess: () => {
		raiseToast(__('Unscreened messages moved to Inbox.'))
		showMoveToInbox.value = false
		mailboxes.reload()
	},
})

const moveToInboxOptions = computed(() => ({
	title: __('Move unscreened messages?'),
	message: __('Screening is off. Move the messages currently in the Screener to your Inbox?'),
	actions: [
		{
			label: __('Move to Inbox'),
			variant: 'solid',
			onClick: () => moveScreeningToInbox.submit(),
			loading: moveScreeningToInbox.loading,
		},
	],
}))

const save = async () => {
	let askMoveToInbox = false
	if (accountDirty.value) {
		const screeningChanged =
			!!accountSettings.doc.enable_screening !==
			!!accountSettings.originalDoc?.enable_screening
		// Turning screening off leaves the already-screened mail in the Screening folder — offer to move
		// it to the inbox (only worth asking when there's something there).
		askMoveToInbox =
			screeningChanged &&
			!accountSettings.doc.enable_screening &&
			(mailboxes.data?.find((m: MailboxData) => m.id === mailboxIds.screening)
				?.total_threads ?? 0) > 0
		await accountSettings.save.submit()
		// Sync the shared user data so compose picks up the new default and the junk flow picks up
		// the "on mark as junk" choice without a page reload (both read from user.data.accounts).
		if (activeAccount) {
			activeAccount.default_outgoing_email = accountSettings.doc.default_outgoing_email
			activeAccount.on_mark_as_junk = accountSettings.doc.on_mark_as_junk
			activeAccount.enable_screening = !!accountSettings.doc.enable_screening
			activeAccount.block_remote_images = !!accountSettings.doc.block_remote_images
		}
		// Enabling screening creates the Screening folder server-side; reload so it shows up.
		if (screeningChanged) mailboxes.reload()
	}
	if (userDirty.value) await userSettings.save.submit()
	raiseToast(__('Account updated.'))
	if (askMoveToInbox) showMoveToInbox.value = true
}
</script>
