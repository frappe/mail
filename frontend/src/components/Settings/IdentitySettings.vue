<template>
	<template v-if="identities?.data?.length">
		<div class="flex min-h-full flex-col">
			<div class="flex-1 space-y-4 overflow-y-auto">
				<h1>{{ __('Identity') }}</h1>

				<FormControl
					v-model="identityName"
					type="combobox"
					:label="__('Email')"
					variant="outline"
					:options="
						identities.data.map((identity: Identity) => ({
							label: identity.email,
							value: identity.name,
						}))
					"
					:open-on-click="true"
				/>

				<template v-if="identity?.doc && !identity.loading">
					<FormControl
						v-model="identity.doc._name"
						:label="__('Display Name')"
						variant="outline"
					/>

					<div class="space-y-1.5">
						<label class="text-ink-gray-5 block text-xs"> {{ __('Reply To') }} </label>
						<IdentitySettingsListView
							:data="identity.doc.reply_to || []"
							:empty-state-description="__('No Reply To addresses added.')"
							@delete="(index: number) => identity.doc.reply_to.splice(index, 1)"
						/>
					</div>
					<Button
						:label="__('Add Reply To')"
						class="min-h-7 w-full"
						variant="outline"
						@click="() => showAddEmailAddress(true)"
					/>

					<div class="space-y-1.5">
						<label class="text-ink-gray-5 block text-xs"> {{ __('Bcc') }} </label>
						<IdentitySettingsListView
							:data="identity.doc.bcc || []"
							:empty-state-description="__('No Bcc addresses added.')"
							@delete="(index: number) => identity.doc.bcc.splice(index, 1)"
						/>
					</div>
					<Button
						:label="__('Add Bcc')"
						class="min-h-7 w-full"
						variant="outline"
						@click="() => showAddEmailAddress(false)"
					/>

					<FormControl
						v-if="signatures.data?.length"
						v-model="savedSignature"
						type="combobox"
						:label="__('Use Saved Signature')"
						:options="
							signatures.data?.map((sig) => ({
								label: sig.signature_name,
								value: sig.html_body,
							}))
						"
						variant="outline"
						:open-on-click="true"
						@update:model-value="(val: string) => (identity.doc.html_signature = val)"
					/>

					<div class="space-y-1.5">
						<label class="text-ink-gray-5 block text-xs">
							{{ __('Default Signature') }}
						</label>
						<TextEditor
							editor-class="prose-sm min-h-[8rem] border rounded-b-lg border-t-0 p-2 max-w-none border-outline-gray-2"
							:extensions="[CustomParagraphExtension]"
							:fixed-menu="buttons"
							:placeholder="__('Write your signature here')"
							:content="identity.doc.html_signature"
							@change="(val: string) => (identity.doc.html_signature = val)"
						/>
					</div>
				</template>
			</div>

			<div v-if="identity?.doc && !identity.loading" class="sticky bottom-0 bg-white py-4">
				<Button
					:label="__('Save')"
					variant="solid"
					:disabled="
						identity.get.loading ||
						JSON.stringify(identity.doc) === JSON.stringify(identity.originalDoc)
					"
					:loading="identity.save.loading"
					class="min-h-7 w-full"
					@click="save"
				/>
			</div>

			<Dialog
				v-model="showDialog"
				:options="{
					title: isAddReplyTo ? __('New Reply To') : __('New Bcc'),
					actions: [
						{
							label: __('Save'),
							variant: 'solid',
							disabled: !email,
							onClick: () => addEmailAddress(),
						},
					],
				}"
			>
				<template #body-content>
					<FormControl
						v-model="email"
						:label="__('Email')"
						placeholder="johndoe@example.com"
						type="email"
						class="mb-4 w-full"
						:required="true"
					/>
					<FormControl
						v-model="displayName"
						:label="__('Display Name')"
						placeholder="John Doe"
						class="w-full"
					/>
				</template>
			</Dialog>
		</div>
	</template>
</template>

<script setup lang="ts">
import { inject, ref, watch } from 'vue'
import {
	Button,
	Dialog,
	FormControl,
	TextEditor,
	createDocumentResource,
	useList,
} from 'frappe-ui'

import { convertHtmlToText, raiseToast } from '@/utils'
import { useTextEditorButtons } from '@/utils/composables'
import { CustomParagraphExtension } from '@/utils/text-editor'
import { userStore } from '@/stores/user'
import IdentitySettingsListView from '@/components/IdentitySettingsListView.vue'

import type { Identity } from '@/types'

const user = inject('$user')
const { identities } = userStore()

const { buttons } = useTextEditorButtons()

const signatures = useList({
	doctype: 'Mail Signature',
	immediate: true,
	fields: ['name', 'signature_name', 'html_body'],
	filters: { account: user.data.name },
	cacheKey: ['mailSignatures', user.data.name],
})

const identityName = ref(identities.data?.[0]?.name || '')

const getIdentity = () =>
	createDocumentResource({
		doctype: 'Identity',
		name: identityName.value,
		setValue: {
			onSuccess: () => {
				raiseToast(__('Identity updated.'))
				identities.reload()
			},
			onError: (error) => raiseToast(error.messages[0], 'error'),
		},
	})

const save = () => {
	identity.value.doc.text_signature = convertHtmlToText(identity.value.doc.html_signature)
	identity.value.save.submit()
}

const identity = ref(getIdentity())
const savedSignature = ref('')

const showDialog = ref(false)
const isAddReplyTo = ref(true)
const email = ref('')
const displayName = ref('')

const showAddEmailAddress = (isReplyTo: boolean) => {
	email.value = ''
	displayName.value = ''
	isAddReplyTo.value = isReplyTo
	showDialog.value = true
}

const addEmailAddress = () => {
	if (isAddReplyTo.value)
		identity.value.doc.reply_to.push({ email: email.value, display_name: displayName.value })
	else identity.value.doc.bcc.push({ email: email.value, display_name: displayName.value })
	showDialog.value = false
}

watch(identityName, (val) => {
	if (val) identity.value = getIdentity()
})
</script>
