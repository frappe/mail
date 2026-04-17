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
			@click="handleSave"
		/>
		<Dialog v-model="showConfirmDialog" :options="confirmDialogOptions" />
	</template>
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import {
	Button,
	Dialog,
	FormControl,
	Switch,
	TextEditor,
	createDocumentResource,
	createResource,
} from 'frappe-ui'

import { convertHtmlToText, raiseToast } from '@/utils'
import { useTextEditorButtons } from '@/utils/composables'
import { userStore } from '@/stores/user'

import type { VacationResponse } from '@/types/doctypes'

const user = inject('$user')
const dayjs = inject('$dayjs')

const { buttons } = useTextEditorButtons()

const showConfirmDialog = ref(false)

const { sieveScripts } = userStore()

const activeSieveScript = computed(
	() => sieveScripts.data?.find((s) => s.active && s._name !== 'vacation')?._name,
)

const handleSave = () => {
	if (activeSieveScript.value && vacationResponse.doc.enabled) showConfirmDialog.value = true
	else updateVacationResponse.submit()
}

const vacationResponse = createDocumentResource({
	doctype: 'Vacation Response',
	name: user.data.name,
	transform: (doc: VacationResponse) => {
		doc['enabled'] = !!doc['enabled']
		if (doc['from_date']) doc['from_date'] = dayjs(doc['from_date']).format('YYYY-MM-DDTHH:mm')
		if (doc['to_date']) doc['to_date'] = dayjs(doc['to_date']).format('YYYY-MM-DDTHH:mm')
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
		sieveScripts.reload()
		raiseToast(__('Vacation response updated.'))
	},
	onError: (error) => raiseToast(error.messages[0], 'error'),
})

const confirmDialogOptions = computed(() => ({
	title: confirmTitle.value,
	message: confirmMessage.value,
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [
		{
			label: __('Yes, enable Vacation Response'),
			onClick: () => {
				updateVacationResponse.submit()
				showConfirmDialog.value = false
			},
		},
		{
			label: __('Cancel'),
			variant: 'outline',
			onClick: () => {
				vacationResponse.doc.enabled = false
				showConfirmDialog.value = false
			},
		},
	],
}))

const confirmTitle = computed(() => {
	if (activeSieveScript.value === 'Folder Automation') return __('Disable Folder Automation?')
	return __('Active Sieve Script Detected')
})

const confirmMessage = computed(() => {
	if (activeSieveScript.value === 'Folder Automation')
		return __(
			'Enabling Vacation Response will disable Folder Automation. Do you want to proceed?',
		)

	return __(
		"Enabling Vacation Response will deactivate sieve script '{0}'. Do you want to proceed?",
		[activeSieveScript.value],
	)
})
</script>
