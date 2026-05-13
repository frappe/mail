<template>
	<template v-if="vacationResponse.data">
		<h1>{{ __('Vacation Response') }}</h1>
		<Switch
			v-model="vacationResponse.data.enabled"
			:label="__('Enabled')"
			:description="__('Auto-reply to incoming mails while you’re away.')"
			class="!p-0"
		/>
		<FormControl
			v-model="vacationResponse.data.from_date"
			type="datetime-local"
			:label="__('From Date')"
			variant="outline"
		/>
		<FormControl
			v-model="vacationResponse.data.to_date"
			type="datetime-local"
			:label="__('To Date')"
			variant="outline"
		/>
		<FormControl
			v-model="vacationResponse.data.subject"
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
				:content="vacationResponse.data.html_body"
				@change="(val: string) => (vacationResponse.data.html_body = val)"
			/>
		</div>
		<Button
			:label="__('Save')"
			variant="solid"
			:disabled="
				vacationResponse.loading ||
				JSON.stringify(vacationResponse.data) === JSON.stringify(original)
			"
			:loading="updateVacationResponse.loading"
			class="min-h-7"
			@click="handleSave"
		/>
		<SetSieveScriptStateModal
			v-model="showConfirmDialog"
			:script="{ _name: 'vacation', active: 0 }"
			:action="updateVacationResponse.submit"
		/>
	</template>
</template>

<script setup lang="ts">
import { computed, inject, reactive, ref } from 'vue'
import { Button, FormControl, Switch, TextEditor, createResource } from 'frappe-ui'

import { convertHtmlToText, raiseToast } from '@/utils'
import { useTextEditorButtons } from '@/utils/composables'
import { userStore } from '@/stores/user'
import SetSieveScriptStateModal from '@/components/Modals/SetSieveScriptStateModal.vue'

import type { VacationResponse } from '@/types/doctypes'

const store = userStore()
const dayjs = inject('$dayjs')

const { buttons } = useTextEditorButtons()

const showConfirmDialog = ref(false)

const activeSieveScript = computed(
	() => store.sieveScripts.data?.find((s) => s.active && s._name !== 'vacation')?._name,
)

const handleSave = () => {
	if (activeSieveScript.value && vacationResponse.data.enabled) showConfirmDialog.value = true
	else updateVacationResponse.submit()
}

const original = reactive({})

const vacationResponse = createResource({
	url: 'mail.client.doctype.vacation_response.vacation_response.get_vacation_response',
	makeParams: () => ({ account: store.account }),
	auto: true,
	transform: (doc: VacationResponse) => {
		doc['enabled'] = !!doc['enabled']
		if (doc['from_date']) doc['from_date'] = dayjs(doc['from_date']).format('YYYY-MM-DDTHH:mm')
		if (doc['to_date']) doc['to_date'] = dayjs(doc['to_date']).format('YYYY-MM-DDTHH:mm')
		Object.assign(original, doc)
		return doc
	},
})

const updateVacationResponse = createResource({
	url: 'mail.client.doctype.vacation_response.vacation_response.update_vacation_response',
	makeParams: () => ({
		account: store.account,
		enabled: vacationResponse.data.enabled,
		from_date: vacationResponse.data.from_date,
		to_date: vacationResponse.data.to_date,
		subject: vacationResponse.data.subject,
		text_body: convertHtmlToText(vacationResponse.data.html_body),
		html_body: vacationResponse.data.html_body,
	}),
	onSuccess: () => {
		vacationResponse.reload()
		store.sieveScripts.reload()
		raiseToast(__('Vacation response updated.'))
		showConfirmDialog.value = false
	},
	onError: (error) => {
		raiseToast(error.messages[0], 'error')
		showConfirmDialog.value = false
	},
})
</script>
