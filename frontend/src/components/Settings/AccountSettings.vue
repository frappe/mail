<template>
	<template v-if="account.doc">
		<h1>{{ __('Outgoing') }}</h1>
		<FormControl
			v-model="account.doc.default_outgoing_email"
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
import { userStore } from '@/stores/user'

import type { Identity } from '@/types'

const user = inject('$user')
const { identities } = userStore()

const account = createDocumentResource({
	doctype: 'User Settings',
	name: user.data?.name,
	setValue: {
		onSuccess: () => raiseToast(__('Account updated.')),
	},
})

const createContactsAfterEmailSubmit = computed({
	get: () => !!account.doc.create_contacts_after_email_submit,
	set: (val: boolean) => (account.doc.create_contacts_after_email_submit = val ? 1 : 0),
})

const destroyEmailAfterSubmit = computed({
	get: () => !!account.doc.destroy_email_after_submit,
	set: (val: boolean) => (account.doc.destroy_email_after_submit = val ? 1 : 0),
})

const destroyNewsletterAfterSubmit = computed({
	get: () => !!account.doc.destroy_newsletter_after_submit,
	set: (val: boolean) => (account.doc.destroy_newsletter_after_submit = val ? 1 : 0),
})
</script>
