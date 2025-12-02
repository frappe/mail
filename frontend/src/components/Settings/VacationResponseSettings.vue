<template>
	<template v-if="account.doc">
		<h1>{{ __('Vacation Response') }}</h1>
		<Switch
			v-model="vacationResponseEnabled"
			:label="__('Enabled')"
			:description="__('Auto-reply to incoming mails while you’re away.')"
		/>
		<FormControl
			v-model="account.doc.vacation_from_date"
			type="datetime-local"
			:label="__('From Date')"
			variant="outline"
		/>
		<FormControl
			v-model="account.doc.vacation_to_date"
			type="datetime-local"
			:label="__('To Date')"
			variant="outline"
		/>
		<FormControl
			v-model="account.doc.vacation_response_subject"
			:label="__('Subject')"
			placeholder="Out of Office"
			variant="outline"
		/>
		<div class="space-y-1.5">
			<label class="text-ink-gray-5 block text-xs">{{ __('Message') }}</label>
			<TextEditor
				editor-class="prose-sm min-h-[8rem] border rounded-b-lg border-t-0 p-2 max-w-none border-outline-gray-2"
				:placeholder="__('Type something...')"
				:fixed-menu="buttons"
				:content="account.doc.vacation_response_html_body"
				@change="(val: string) => (account.doc.vacation_response_html_body = val)"
			/>
		</div>
		<Button
			:label="__('Save')"
			variant="solid"
			:disabled="
				account.get.loading ||
				JSON.stringify(account.doc) === JSON.stringify(account.originalDoc)
			"
			:loading="account.setVacationResponse?.loading"
			class="min-h-7"
			@click="() => account.setVacationResponse.submit()"
		/>
	</template>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { Button, FormControl, Switch, TextEditor, createDocumentResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { useTextEditorButtons } from '@/utils/composables'

import type { MailAccount } from '@/types/doctypes'

const user = inject('$user')
const dayjs = inject('$dayjs')

const { buttons } = useTextEditorButtons()

const account = createDocumentResource({
	doctype: 'Mail Account',
	name: user.data.name,
	transform: (doc: MailAccount) => {
		doc['vacation_from_date'] = dayjs(doc['vacation_from_date']).format('YYYY-MM-DDTHH:mm')
		doc['vacation_to_date'] = dayjs(doc['vacation_to_date']).format('YYYY-MM-DDTHH:mm')
	},
	whitelistedMethods: {
		setVacationResponse: {
			method: 'set_vacation_response',
			makeParams: () => ({
				enabled: account.doc.vacation_response_enabled,
				from_date: account.doc.vacation_from_date,
				to_date: account.doc.vacation_to_date,
				subject: account.doc.vacation_response_subject,
				html_body: account.doc.vacation_response_html_body,
			}),
			onSuccess: () => {
				account.reload()
				raiseToast(__('Vacation response updated.'))
			},
			onError: (error) => raiseToast(error.messages[0], 'error'),
		},
	},
})

const vacationResponseEnabled = computed({
	get: () => !!account.doc.vacation_response_enabled,
	set: (val: boolean) => (account.doc.vacation_response_enabled = val ? 1 : 0),
})
</script>
