<template>
	<template v-if="vacationResponse.doc">
		<h1>{{ __('Vacation Response') }}</h1>
		<Switch
			v-model="vacationResponse.doc.enabled"
			:label="__('Enabled')"
			:description="__('Auto-reply to incoming mails while you’re away.')"
			class="!p-0"
		/>
		<FormControl
			v-model="vacationResponse.doc.from_date"
			type="datetime-local"
			:label="__('From Date')"
			variant="outline"
		/>
		<FormControl
			v-model="vacationResponse.doc.to_date"
			type="datetime-local"
			:label="__('To Date')"
			variant="outline"
		/>
		<FormControl
			v-model="vacationResponse.doc.subject"
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
				:content="vacationResponse.doc.html_body"
				@change="(val: string) => (vacationResponse.doc.html_body = val)"
			/>
		</div>
		<Button
			:label="__('Save')"
			variant="solid"
			:disabled="
				vacationResponse.get.loading ||
				JSON.stringify(vacationResponse.doc) ===
					JSON.stringify(vacationResponse.originalDoc)
			"
			:loading="updateVacationResponse.loading"
			class="min-h-7"
			@click="() => updateVacationResponse.submit()"
		/>
	</template>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import {
	Button,
	FormControl,
	Switch,
	TextEditor,
	createDocumentResource,
	createResource,
} from 'frappe-ui'

import { convertHtmlToText, raiseToast } from '@/utils'
import { useTextEditorButtons } from '@/utils/composables'

import type { MailAccount } from '@/types/doctypes'

const user = inject('$user')
const dayjs = inject('$dayjs')

const { buttons } = useTextEditorButtons()

const vacationResponse = createDocumentResource({
	doctype: 'Vacation Response',
	name: user.data.name,
	transform: (doc: MailAccount) => {
		doc['enabled'] = !!doc['enabled']
		doc['from_date'] = dayjs(doc['from_date']).format('YYYY-MM-DDTHH:mm')
		doc['to_date'] = dayjs(doc['to_date']).format('YYYY-MM-DDTHH:mm')
	},
})

const updateVacationResponse = createResource({
	url: 'mail.client.doctype.vacation_response.vacation_response.update_vacation_response',
	makeParams: () => ({
		user: user.data.name,
		enabled: vacationResponse.doc.enabled,
		from_date: vacationResponse.doc.from_date,
		to_date: vacationResponse.doc.to_date,
		subject: vacationResponse.doc.subject,
		text_body: convertHtmlToText(vacationResponse.doc.html_body),
		html_body: vacationResponse.doc.html_body,
	}),
	onSuccess: () => {
		vacationResponse.reload()
		raiseToast(__('Vacation response updated.'))
	},
	onError: (error) => raiseToast(error.messages[0], 'error'),
})
</script>
