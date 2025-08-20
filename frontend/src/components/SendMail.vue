<template>
	<component
		:is="isMobile ? SendMailMobileLayout : Dialog"
		v-model="show"
		:options="{ title: __('Send Mail'), size: '4xl' }"
	>
		<template #body-content>
			<TextEditor
				ref="textEditor"
				:editor-class="[
					'prose-sm max-w-none',
					'min-h-[15rem]',
					'[&_p.reply-to-content]:hidden',
				]"
				:extensions="[CustomImageExtension]"
				:content="mail.html_body"
				@change="(val: string) => (mail.html_body = val)"
			>
				<template #top>
					<div class="flex flex-col gap-3 border-b">
						<div class="flex items-center gap-2 sm:border-t sm:pt-2.5">
							<span class="text-ink-gray-4 text-xs">{{ __('From') }}:</span>
							<AutocompleteControl
								v-model="mail.from_email"
								:options="user.data?.email_addresses || []"
							/>
						</div>
						<div class="flex items-center gap-2">
							<span class="text-ink-gray-4 text-xs">{{ __('To') }}:</span>
							<MultiselectInputControl
								v-model="mail.to"
								class="flex-1 text-sm"
								:validate="validateEmail"
								:error-message="
									(value: string) =>
										__(`'{0}' is an invalid email address`, [value])
								"
							/>
							<div class="flex gap-1.5">
								<Button
									:label="__('Cc')"
									variant="ghost"
									:class="
										cc
											? '!bg-surface-gray-4 hover:bg-surface-gray-3'
											: '!text-ink-gray-4'
									"
									@click="toggleCC()"
								/>
								<Button
									:label="__('Bcc')"
									variant="ghost"
									:class="
										bcc
											? '!bg-surface-gray-4 hover:bg-surface-gray-3'
											: '!text-ink-gray-4'
									"
									@click="toggleBCC()"
								/>
							</div>
						</div>
						<div v-if="cc" class="flex items-center gap-2">
							<span class="text-ink-gray-4 text-xs">{{ __('Cc') }}:</span>
							<MultiselectInputControl
								ref="ccInput"
								v-model="mail.cc"
								class="flex-1 text-sm"
								:validate="validateEmail"
								:error-message="
									(value: string) =>
										__(`'{0}' is an invalid email address`, [value])
								"
							/>
						</div>
						<div v-if="bcc" class="flex items-center gap-2">
							<span class="text-ink-gray-4 text-xs">{{ __('Bcc') }}:</span>
							<MultiselectInputControl
								ref="bccInput"
								v-model="mail.bcc"
								class="flex-1 text-sm"
								:validate="validateEmail"
								:error-message="
									(value: string) =>
										__(`'{0}' is an invalid email address`, [value])
								"
							/>
						</div>
						<div class="flex items-center gap-2 pb-2.5">
							<span class="text-ink-gray-4 text-xs">{{ __('Subject') }}:</span>
							<input
								v-model="mail.subject"
								class="bg-surface-white sm:bg-surface-modal flex-1 border-none text-base focus-visible:!ring-0"
							/>
						</div>
					</div>
				</template>
				<template #editor="{ editor }">
					<div
						class="flex h-[calc(100dvh-16.9rem)] flex-col overflow-y-auto py-2.5 text-sm sm:max-h-[40vh]"
						:class="{
							'h-[calc(100dvh-19.7rem)]': cc || bcc,
							'h-[calc(100dvh-21.9rem)]': cc && bcc,
						}"
					>
						<EditorContent :editor="editor" />

						<!-- Attachments -->
						<div class="text-ink-gray-6 mt-auto flex flex-col gap-2.5 pt-2.5">
							<a
								v-for="(file, index) in mail.attachments.filter(
									(file: Attachment) => file.disposition === 'attachment',
								)"
								:key="index"
								class="bg-surface-gray-2 flex cursor-pointer items-center rounded p-2.5"
								:href="file.file_url"
								target="_blank"
								@click="openAttachment(file.blob_id, file.type)"
							>
								<span class="mr-1 font-medium">
									{{ file.file_name || file.filename || file.name }}
								</span>
								<span class="mr-1 font-extralight">
									({{ formatBytes(file.file_size || file.size) }})
								</span>
								<FeatherIcon
									class="ml-auto h-3.5 w-3.5"
									name="x"
									@click.stop.prevent="mail.attachments.splice(index, 1)"
								/>
							</a>
						</div>
					</div>
				</template>
				<template #bottom>
					<FileUploader
						:class="{ 'fixed bottom-0 left-0 right-0 px-3': isMobile }"
						:upload-args="{ private: true, folder: 'Home/Frappe Mail' }"
						@success="
							(file) => mail.attachments.push({ ...file, disposition: 'attachment' })
						"
					>
						<template
							#default="{ file, progress, uploading, openFileSelector, error }"
						>
							<div
								v-if="uploading"
								class="bg-surface-gray-2 text-ink-gray-6 mb-2 rounded p-2.5 text-sm"
							>
								<div class="mb-1.5 flex items-center">
									<span class="mr-1 font-medium"> {{ file.name }} </span>
									<span class="font-extralight">
										({{ formatBytes(file.size) }})
									</span>
								</div>
								<Progress :value="progress" />
							</div>

							<ErrorMessage :message="error" class="mb-2.5" />

							<div
								class="flex flex-wrap justify-between gap-2 overflow-hidden border-t py-2.5"
							>
								<!-- Text editor buttons -->
								<div class="flex items-center gap-1 overflow-x-auto">
									<TextEditorFixedMenu
										:buttons="textEditorButtons"
										class="sm:!bg-surface-modal"
									/>
									<EmojiPicker
										v-if="!isMobile"
										v-slot="{ togglePopover }"
										v-model="emoji"
										@update:model-value="() => appendEmoji()"
									>
										<Button variant="ghost" @click="togglePopover()">
											<template #icon>
												<Laugh class="h-4 w-4" />
											</template>
										</Button>
									</EmojiPicker>
									<Button variant="ghost" @click="openFileSelector()">
										<template #icon>
											<Paperclip class="h-4" />
										</template>
									</Button>
								</div>

								<!-- Send & Discard -->
								<div class="ml-auto flex items-center space-x-2 sm:mt-0">
									<Button :label="__('Discard')" @click="discardMail" />
									<Button
										variant="solid"
										:label="__('Send')"
										@click="sendMail"
									/>
								</div>
							</div>
						</template>
					</FileUploader>
				</template>
			</TextEditor>
		</template>
	</component>
</template>
<script setup lang="ts">
import { computed, inject, nextTick, reactive, ref, useTemplateRef, watch } from 'vue'
import { EditorContent } from '@tiptap/vue-3'
import { Laugh, Paperclip } from 'lucide-vue-next'
import {
	Button,
	Dialog,
	ErrorMessage,
	FeatherIcon,
	FileUploader,
	Progress,
	TextEditor,
	TextEditorFixedMenu,
	createResource,
} from 'frappe-ui'
import { ImageExtension } from 'frappe-ui/src/components/TextEditor/extensions/image'
import { useFileUpload } from 'frappe-ui/src/utils/useFileUpload'

import { formatBytes, textEditorButtons, validateEmail } from '@/utils'
import { useScreenSize } from '@/utils/composables'
import AutocompleteControl from '@/components/Controls/AutocompleteControl.vue'
import MultiselectInputControl from '@/components/Controls/MultiselectInputControl.vue'
import EmojiPicker from '@/components/EmojiPicker.vue'
import SendMailMobileLayout from '@/components/SendMailMobileLayout.vue'

import type { Attachment, ComposeMailData, File as FileDoc, UserResource } from '@/types'

const show = defineModel<boolean>()

const { mailID, mailDetails } = defineProps<{ mailID?: string; mailDetails?: ComposeMailData }>()

const emit = defineEmits(['reloadMails'])

const user = inject('$user') as UserResource
const { isMobile } = useScreenSize()

const textEditor = useTemplateRef('textEditor')
const editor = computed(() => textEditor.value.editor)

const ccInput = ref(null)
const cc = ref(false)
const toggleCC = () => {
	cc.value = !cc.value
	if (cc.value) nextTick(() => ccInput.value.setFocus())
}

const bccInput = ref(null)
const bcc = ref(false)
const toggleBCC = () => {
	bcc.value = !bcc.value
	if (bcc.value) nextTick(() => bccInput.value.setFocus())
}

const emoji = ref()
const appendEmoji = () => {
	editor.value.commands.insertContent(emoji.value)
	editor.value.commands.focus()
	emoji.value = ''
}

const emptyMail = {
	name: '',
	from_email: user.data.default_outgoing,
	to: [],
	cc: [],
	bcc: [],
	attachments: [],
	subject: '',
	html_body: '',
	in_reply_to: '',
	in_reply_to_id: '',
}

const mail = reactive<ComposeMailData>({ ...emptyMail })

const createMail = createResource({
	url: 'mail.api.mail.create_mail',
	makeParams: ({ saveAsDraft }: { saveAsDraft: boolean }) => ({
		...mail,
		save_as_draft: saveAsDraft,
	}),
})

const updateDraftMail = createResource({
	url: 'mail.api.mail.update_draft_mail',
	makeParams: ({ submit }: { submit: boolean }) => ({ ...mail, submit: submit }),
})

const deleteMail = createResource({
	url: 'mail.api.mail.delete_mail',
	makeParams: () => ({ _id: mailID }),
	onSuccess: () => emit('reloadMails'),
})

const saveDraft = ref(true)

const sendMail = () => {
	saveDraft.value = false
	show.value = false
	if (mailID) updateDraftMail.submit({ submit: true })
	else createMail.submit({ saveAsDraft: false })
}

const discardMail = () => {
	saveDraft.value = false
	show.value = false
	if (mailID) deleteMail.submit()
}

const setMailDetails = () => {
	if (!mailDetails) {
		Object.assign(mail, emptyMail)
		mail.attachments = []
		return
	}

	if (mailDetails.from_email) mail.from_email = mailDetails.from_email
	mail.name = mailDetails.name
	mail.in_reply_to = mailDetails.in_reply_to
	mail.in_reply_to_id = mailDetails.in_reply_to_id
	mail.subject = mailDetails.subject
	mail.html_body = mailDetails.html_body
	mail.attachments = mailDetails.attachments
	mail.to = mailDetails.to
	mail.cc = mailDetails.cc
	mail.bcc = mailDetails.bcc

	cc.value = !!mail.cc?.length
	bcc.value = !!mail.bcc?.length
}

watch(show, (val) => {
	if (val) return setMailDetails()

	if (!saveDraft.value) return (saveDraft.value = true)

	if (mailID) updateDraftMail.submit({ submit: false })
	else if (!isMailEmpty.value) createMail.submit({ saveAsDraft: true })
})

const isMailEmpty = computed(() => {
	const isSubjectEmpty = !mail.subject.length
	const isAttachmentsEmpty = !mail.attachments.length
	const isRecipientsEmpty = [mail.to, mail.cc, mail.bcc].every((d) => !d.length)

	let isBodyEmpty = true
	if (mail.html_body) {
		const element = document.createElement('div')
		element.innerHTML = mail.html_body
		isBodyEmpty =
			!element.textContent?.trim() &&
			Array.from(element.children).every((d) => !d.textContent?.trim())
	}

	return isSubjectEmpty && isRecipientsEmpty && isAttachmentsEmpty && isBodyEmpty
})

const fetchAttachment = createResource({
	url: 'mail.api.mail.fetch_attachment',
	makeParams: (blob_id: string) => ({ blob_id }),
})

const openAttachment = async (blob_id?: string, type?: string) => {
	if (!blob_id) return

	const data = await fetchAttachment.submit(blob_id)
	const byteArray = new Uint8Array(data)
	const blob = new Blob([byteArray], { type })
	const url = URL.createObjectURL(blob)
	window.open(url, '_blank')
}

const uploadFunction = async (file: File) => {
	const fileUpload = useFileUpload()
	const fileDoc = (await fileUpload.upload(file, {
		private: true,
		folder: 'Home/Frappe Mail',
	})) as FileDoc
	mail.attachments.push({
		file_name: fileDoc.file_name,
		file_url: fileDoc.file_url,
		disposition: 'inline',
	})
	return { src: fileDoc.file_url }
}

const CustomImageExtension = ImageExtension.extend({
	addOptions: () => ({ uploadFunction }),
	addAttributes: () => ({
		'data-cid': {
			default: null,
			parseHTML: (element) => element.getAttribute('data-cid'),
			renderHTML: (attributes) =>
				attributes['data-cid'] ? { 'data-cid': attributes['data-cid'] } : {},
		},
	}),
})
</script>
