<template>
	<TextEditor
		ref="textEditor"
		editor-class="not-prose prose-sm max-w-none"
		:extensions="[CustomImageExtension]"
		:content="mail.html_body"
		@change="(val: string) => (mail.html_body = val)"
	>
		<template #top>
			<div class="flex flex-col gap-2.5 border-b pb-2.5">
				<div v-if="!mailDetails?.type" class="flex items-center gap-2">
					<span class="text-ink-gray-4 text-xs">{{ __('From') }}:</span>
					<AutocompleteControl
						v-model="mail.from_email"
						:options="user.data?.email_addresses || []"
					/>
				</div>
				<div class="flex items-start gap-2">
					<Dropdown
						v-if="isInThread && mailDetails?.type"
						:options="THREAD_MAIL_ACTIONS"
					>
						<Button variant="ghost" :icon="TYPE_ICON_MAP[mailDetails.type]"> </Button>
					</Dropdown>
					<div class="flex flex-1 flex-col gap-2.5">
						<div class="flex items-center gap-2">
							<span class="text-ink-gray-4 text-xs">{{ __('To') }}:</span>
							<MultiselectInputControl
								ref="toInput"
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
					</div>
				</div>
				<div v-if="!mailDetails?.type" class="flex items-center gap-2">
					<span class="text-ink-gray-4 text-xs">{{ __('Subject') }}:</span>
					<input
						v-model="mail.subject"
						class="flex-1 border-none bg-inherit text-base focus-visible:!ring-0"
					/>
				</div>
			</div>
		</template>
		<template #editor="{ editor }">
			<div class="flex flex-col overflow-y-auto py-2.5 text-sm">
				<EditorContent :editor="editor" />

				<!-- Show quoted content -->
				<Button
					v-if="mail?.quoted_content"
					label="&middot;&middot;&middot;"
					class="max-h-4 w-fit"
					@click="openQuotedContent"
				/>

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
				:class="{
					'fixed left-0 right-0 z-20 px-3 transition-all': isMobile,
				}"
				:style="{ bottom: `${toolbarBottom}px` }"
				:upload-args="{ private: true, folder: 'Home/Frappe Mail' }"
				@success="(file) => mail.attachments.push({ ...file, disposition: 'attachment' })"
			>
				<template #default="{ file, progress, uploading, openFileSelector, error }">
					<div
						v-if="uploading"
						class="bg-surface-gray-2 text-ink-gray-6 mb-2 rounded p-2.5 text-sm"
					>
						<div class="mb-1.5 flex items-center">
							<span class="mr-1 font-medium"> {{ file.name }} </span>
							<span class="font-extralight"> ({{ formatBytes(file.size) }}) </span>
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
								class="!bg-inherit"
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
						<div v-if="!isMobile" class="ml-auto flex items-center space-x-2">
							<Button
								:label="__('Discard')"
								:icon-left="Trash2"
								@click="discardMail"
							/>
							<Button
								:label="__('Save Draft')"
								:icon-left="Save"
								:disabled="!isDraftUpdated"
								:loading="createMail.loading || updateDraft.loading"
								@click="saveDraft"
							/>
							<Button
								variant="solid"
								:label="__('Send')"
								:disabled="isRecipientsEmpty"
								:icon-left="SendHorizontal"
								@click="sendMail"
							/>
						</div>
					</div>
				</template>
			</FileUploader>
		</template>
	</TextEditor>
</template>

<script setup lang="ts">
import {
	computed,
	inject,
	nextTick,
	onMounted,
	onUnmounted,
	reactive,
	ref,
	useTemplateRef,
} from 'vue'
import { EditorContent } from '@tiptap/vue-3'
import {
	Edit,
	ExternalLink,
	Forward,
	Laugh,
	Paperclip,
	Reply,
	ReplyAll,
	Save,
	SendHorizontal,
	Trash2,
} from 'lucide-vue-next'
import {
	Button,
	Dropdown,
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

import type { Attachment, ComposeMailData, File as FileDoc, UserResource } from '@/types'

const show = defineModel<boolean>()

const {
	mailID,
	mailDetails,
	isInThread = false,
} = defineProps<{ mailID?: string; mailDetails?: ComposeMailData; isInThread?: boolean }>()

const emit = defineEmits(['reloadMails', 'discardMail', 'reply', 'replyAll', 'forward'])

const user = inject('$user') as UserResource
const { isMobile } = useScreenSize()

const textEditor = useTemplateRef('textEditor')
const editor = computed(() => textEditor.value.editor)

const toInput = useTemplateRef('toInput')
const ccInput = useTemplateRef('ccInput')
const bccInput = useTemplateRef('bccInput')

const cc = ref(!!mailDetails?.cc?.length)
const toggleCC = () => {
	cc.value = !cc.value
	if (cc.value) nextTick(() => ccInput.value?.setFocus())
}

const bcc = ref(!!mailDetails?.bcc?.length)
const toggleBCC = () => {
	bcc.value = !bcc.value
	if (bcc.value) nextTick(() => bccInput.value?.setFocus())
}

const emoji = ref()
const appendEmoji = () => {
	editor.value.commands.insertContent(emoji.value)
	editor.value.commands.focus()
	emoji.value = ''
}

const mail = reactive<ComposeMailData>({
	name: mailDetails?.name || '',
	from_email: mailDetails?.from_email || user.data.default_outgoing,
	to: mailDetails?.to || [],
	cc: mailDetails?.cc || [],
	bcc: mailDetails?.bcc || [],
	attachments: mailDetails?.attachments || [],
	subject: mailDetails?.subject || '',
	html_body: mailDetails?.html_body || '',
	quoted_content: mailDetails?.quoted_content || '',
	in_reply_to: mailDetails?.in_reply_to || '',
	in_reply_to_id: mailDetails?.in_reply_to_id || '',
})

const originalMail = ref<ComposeMailData>()
onMounted(() => {
	originalMail.value = JSON.parse(JSON.stringify(mail))
	if (mailDetails?.name?.startsWith('draft') && !mailDetails?.in_reply_to)
		setTimeout(() => toInput.value?.setFocus(), 50)
})

const createMail = createResource({
	url: 'mail.api.mail.create_mail',
	makeParams: ({ save_as_draft }: { save_as_draft: boolean }) => ({
		...mail,
		html_body: mail.html_body + mail.quoted_content,
		save_as_draft,
	}),
})

const updateDraft = createResource({
	url: 'mail.api.mail.update_draft_mail',
	makeParams: ({ submit }: { submit: boolean }) => ({
		...mail,
		html_body: mail.html_body + mail.quoted_content,
		submit: submit,
	}),
})

const deleteMail = createResource({
	url: 'mail.api.mail.delete_mail',
	makeParams: () => ({ _id: mailID }),
	onSuccess: () => emit('reloadMails'),
})

const isSaveDraft = ref(true)

const sendMail = () => {
	isSaveDraft.value = false
	show.value = false
	if (mailID) updateDraft.submit({ submit: true })
	else createMail.submit({ save_as_draft: false })
}

const saveDraft = () => {
	if (!isDraftUpdated.value) return

	if (mailID) updateDraft.submit({ submit: false })
	else if (!isMailEmpty.value) createMail.submit({ save_as_draft: true })
}

const discardMail = () => {
	isSaveDraft.value = false
	show.value = false
	if (mailID) deleteMail.submit()
	emit('discardMail')
}

const isDraftUpdated = computed(() => JSON.stringify(mail) !== JSON.stringify(originalMail.value))

onUnmounted(() => {
	if (!isSaveDraft.value) return (isSaveDraft.value = true)
	saveDraft()
})

const THREAD_MAIL_ACTIONS = [
	{
		group: '',
		items: [
			{ label: __('Reply'), icon: Reply, onClick: () => emit('reply') },
			{
				label: __('Reply All'),
				icon: ReplyAll,
				onClick: () => emit('replyAll'),
			},
			{
				label: __('Forward'),
				icon: Forward,
				onClick: () => emit('forward'),
			},
		],
	},
	{
		group: '',
		items: [
			{
				label: __('Edit Subject'),
				icon: Edit,
				onClick: () => console.log('discard-mail'),
			},
			{
				label: __('Pop Out'),
				icon: ExternalLink,
				onClick: () => console.log('discard-mail'),
			},
		],
	},
]

// Make toolbar hover over keyboard on mobile

const toolbarBottom = ref(0)

const updatePosition = () => {
	if (!window.visualViewport) return
	const offset =
		window.innerHeight - window.visualViewport.height - window.visualViewport.offsetTop
	toolbarBottom.value = offset > 0 ? offset : 0
}

onMounted(() => {
	if (!(isMobile.value && window.visualViewport)) return

	window.visualViewport.addEventListener('resize', updatePosition)
	window.visualViewport.addEventListener('scroll', updatePosition)

	updatePosition()

	onUnmounted(() => {
		if (!window.visualViewport) return
		window.visualViewport.removeEventListener('resize', updatePosition)
		window.visualViewport.removeEventListener('scroll', updatePosition)
	})
})

const isRecipientsEmpty = computed(() => [mail.to, mail.cc, mail.bcc].every((d) => !d.length))

const isMailEmpty = computed(() => {
	const isSubjectEmpty = !mail.subject.length
	const isQuotedContentEmpty = !mail.quoted_content?.length
	const isAttachmentsEmpty = !mail.attachments.length

	let isBodyEmpty = true
	if (mail.html_body) {
		const element = document.createElement('div')
		element.innerHTML = mail.html_body
		isBodyEmpty =
			!element.textContent?.trim() &&
			Array.from(element.children).every((d) => !d.textContent?.trim())
	}

	return (
		isSubjectEmpty &&
		isQuotedContentEmpty &&
		isRecipientsEmpty.value &&
		isAttachmentsEmpty &&
		isBodyEmpty
	)
})

const openQuotedContent = () => {
	mail.html_body += mail.quoted_content
	mail.quoted_content = ''
}

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

const TYPE_ICON_MAP = {
	reply: Reply,
	replyAll: ReplyAll,
	forward: Forward,
}
</script>
