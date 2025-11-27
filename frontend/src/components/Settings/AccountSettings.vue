<template>
	<template v-if="account.doc">
		<h1>{{ __('Outgoing') }}</h1>
		<AutocompleteControl
			v-model="account.doc.default_outgoing_email"
			variant="outline"
			:label="__('Send Mails From')"
			:show-search="false"
			:options="user.data.email_addresses"
		/>
		<Switch
			v-model="createMailContact"
			:label="__('Create Mail Contacts')"
			:description="__('Create contacts of people you send mails to.')"
		/>
		<Switch
			v-model="destroyEmailAfterSubmission"
			:label="__('Delete Email After Sending')"
			:description="
				__('Automatically deletes the email from your mailbox after it is sent.')
			"
		/>
		<Switch
			v-model="destroyNewsletterAfterSubmission"
			:label="__('Delete Newsletter After Sending')"
			:description="__('Automatically deletes the newsletter after it is sent.')"
		/>

		<h1>{{ __('Recovery') }}</h1>
		<FormControl
			v-model="account.doc.backup_email"
			:label="__('Backup Email')"
			:description="__(`We'll contact you here if there's an issue with your main account.`)"
			variant="outline"
		/>
		<ErrorMessage :message="account.save.error" />
		<Button
			:label="__('Save')"
			variant="solid"
			:disabled="
				account.get.loading ||
				JSON.stringify(account.doc) === JSON.stringify(account.originalDoc)
			"
			:loading="account.save.loading"
			class="min-h-7"
			@click="() => account.save.submit()"
		/>
	</template>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { Button, ErrorMessage, FormControl, Switch, createDocumentResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import AutocompleteControl from '@/components/Controls/AutocompleteControl.vue'

const user = inject('$user')

const account = createDocumentResource({
	doctype: 'Mail Account',
	name: user.data?.name,
	setValue: {
		onSuccess: () => raiseToast(__('Account settings saved successfully')),
	},
})

const createMailContact = computed({
	get: () => !!account.doc.create_mail_contact,
	set: (val: boolean) => (account.doc.create_mail_contact = val ? 1 : 0),
})

const destroyEmailAfterSubmission = computed({
	get: () => !!account.doc.destroy_email_after_submission,
	set: (val: boolean) => (account.doc.destroy_email_after_submission = val ? 1 : 0),
})

const destroyNewsletterAfterSubmission = computed({
	get: () => !!account.doc.destroy_newsletter_after_submission,
	set: (val: boolean) => (account.doc.destroy_newsletter_after_submission = val ? 1 : 0),
})
</script>
