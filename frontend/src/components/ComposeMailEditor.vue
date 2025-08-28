<template>
	<TextEditor
		ref="textEditor"
		editor-class="not-prose prose-sm max-w-none"
		:extensions="[CustomImageExtension]"
		:content="mail.html_body"
		class="flex flex-col"
		:class="{ 'pointer-events-none opacity-50': !show, 'sm:h-[75vh]': !isInThread }"
		:style="isMobile && { height: editorHeight }"
		@change="(val: string) => (mail.html_body = val)"
	>
		<template #top>
			<div class="flex flex-col gap-2.5 border-b pb-2.5">
				<div v-if="!mailDetails?.type || isMobile" class="flex justify-between gap-2">
					<div class="flex items-center gap-2">
						<span class="text-ink-gray-4 text-xs">{{ __('From') }}:</span>
						<AutocompleteControl
							v-model="mail.from_email"
							:options="user.data?.email_addresses || []"
						/>
					</div>
					<Button
						v-if="isInThread"
						variant="ghost"
						:disabled="isLoading"
						@click="emit('popOut', mail)"
					>
						<template #icon>
							<component :is="ExternalLink" class="text-ink-gray-5 h-4 w-4" />
						</template>
					</Button>
				</div>
				<div class="flex items-start gap-2">
					<Dropdown v-if="isInThread && mailDetails?.type" :options="localDraftActions">
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
				<div v-if="!mailDetails?.type || isMobile" class="flex items-center gap-2">
					<span class="text-ink-gray-4 text-xs">{{ __('Subject') }}:</span>
					<input
						v-model="mail.subject"
						class="flex-1 border-none bg-inherit text-base focus-visible:!ring-0"
					/>
				</div>
			</div>
		</template>
		<template #editor="{ editor }">
			<div
				class="my-2.5 flex flex-1 cursor-text flex-col overflow-y-auto text-sm"
				:class="{ 'max-h-96 min-h-32': isInThread }"
				@click="editor.commands.focus('end')"
			>
				<EditorContent :editor @click.stop />

				<div class="mt-auto cursor-default space-y-2.5 pt-2.5" @click.stop>
					<!-- Show quoted content -->
					<Button
						v-if="mail?.quoted_content"
						label="&middot;&middot;&middot;"
						class="max-h-4 w-fit"
						@click="openQuotedContent"
					/>

					<!-- Attachments -->
					<a
						v-for="(file, index) in mail.attachments.filter(
							(file: Attachment) => file.disposition === 'attachment',
						)"
						:key="index"
						class="bg-surface-gray-2 text-ink-gray-6 flex cursor-pointer items-center rounded p-2.5"
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
			<ComposeMailToolbar
				:is-saving-draft="isSavingDraft"
				:is-loading="isLoading"
				:is-recipients-empty="isRecipientsEmpty"
				@add-attachment="(file) => mail.attachments.push(file)"
				@append-emoji="(emoji: string) => appendEmoji(emoji)"
				@discard-mail="discardMail"
				@send-mail="sendMail"
			/>
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
import { watchDebounced } from '@vueuse/core'
import { ExternalLink, Forward, Reply, ReplyAll } from 'lucide-vue-next'
import { Button, Dropdown, FeatherIcon, TextEditor, createResource } from 'frappe-ui'
import { ImageExtension } from 'frappe-ui/src/components/TextEditor/extensions/image'
import { useFileUpload } from 'frappe-ui/src/utils/useFileUpload'

import { formatBytes, raiseToast, validateEmail } from '@/utils'
import { useScreenSize, useVisualViewport } from '@/utils/composables'
import ComposeMailToolbar from '@/components/ComposeMailToolbar.vue'
import AutocompleteControl from '@/components/Controls/AutocompleteControl.vue'
import MultiselectInputControl from '@/components/Controls/MultiselectInputControl.vue'

import type { Attachment, ComposeMailData, File as FileDoc, UserResource } from '@/types'

const show = defineModel<boolean>()

const { mailDetails, isInThread = false } = defineProps<{
	mailDetails?: ComposeMailData
	isInThread?: boolean
}>()

const emit = defineEmits(['reloadMails', 'discardMail', 'reply', 'replyAll', 'forward', 'popOut'])

// Editor

const { isMobile } = useScreenSize()

const textEditor = useTemplateRef('textEditor')
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

const appendEmoji = (emoji: string) => {
	textEditor.value.editor.commands.insertContent(emoji)
	textEditor.value.editor.commands.focus()
}

const editorHeight = useVisualViewport(
	(viewport) => `${viewport.height - viewport.offsetTop - 112}px`,
)

// Setup & hooks

const user = inject('$user') as UserResource

const mail = reactive<ComposeMailData>({
	name: mailDetails?.name || '',
	_id: mailDetails?._id || '',
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
	forwarded_from_id: mailDetails?.forwarded_from_id || '',
})

const originalMail = ref<ComposeMailData>()
const updateOriginalMail = () => (originalMail.value = JSON.parse(JSON.stringify(mail)))
const isDraftUpdated = computed(() => JSON.stringify(mail) !== JSON.stringify(originalMail.value))

onMounted(() => {
	updateOriginalMail()
	if (mailDetails?.type === 'forward') setTimeout(() => toInput.value?.setFocus(), 50)
})

onUnmounted(() => {
	saveDraft()
	// emit('discardMail')
})

watchDebounced(mail, () => saveDraft(), { debounce: 2000 })

// Actions

const isSavingDraft = ref(false)

const saveDraft = async () => {
	if (!isDraftUpdated.value || isLoading.value) return

	isSavingDraft.value = true
	if (mail._id) await updateDraft.submit()
	else if (!isMailEmpty.value) await createMail.submit()
	isSavingDraft.value = false
}

const sendMail = () => {
	if (isRecipientsEmpty.value) return raiseToast(__('Please add at least one recipient.'))
	show.value = false
	if (mail._id) updateDraft.submit()
	else createMail.submit()
}

const discardMail = () => {
	show.value = false
	if (mail._id) deleteMail.submit()
	else emit('discardMail')
}

defineExpose({ sendMail, discardMail })

const onMailUpdateSuccess = ({ _id, save_as_draft }: { _id: string; save_as_draft: boolean }) => {
	mail._id = _id
	updateOriginalMail()
	if (!show.value) raiseToast(save_as_draft ? __('Draft saved.') : __('Message sent.'))
}

// Resources

const createMail = createResource({
	url: 'mail.api.mail.create_mail',
	makeParams: () => ({
		...mail,
		html_body: mail.html_body + mail.quoted_content,
		save_as_draft: isSavingDraft.value,
	}),
	onSuccess: onMailUpdateSuccess,
})

const updateDraft = createResource({
	url: 'mail.api.mail.update_draft_mail',
	makeParams: () => ({
		...mail,
		html_body: mail.html_body + mail.quoted_content,
		submit: !isSavingDraft.value,
	}),
	onSuccess: onMailUpdateSuccess,
})

const deleteMail = createResource({
	url: 'mail.api.mail.delete_mail',
	makeParams: () => ({ _id: mail._id }),
	onSuccess: () => {
		emit('reloadMails')
		raiseToast(__('Draft discarded.'))
	},
})

const isLoading = computed(() => createMail.loading || updateDraft.loading || deleteMail.loading)

// Local draft actions

const localDraftActions = computed(() => [
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
				label: __('Pop Out'),
				icon: ExternalLink,
				onClick: () => emit('popOut', mail),
				condition: () => !isLoading.value,
			},
		],
	},
])

// Mail content

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

// Attachments

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
	name: 'customImage',
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
