<template>
	<TextEditor
		ref="textEditor"
		editor-class="prose-sm max-w-none"
		:extensions="[CustomImageExtension, CustomParagraphExtension]"
		:content="mail.html_body.replaceAll('<div><br></div>', '<div></div>')"
		class="flex flex-col max-sm:overflow-y-auto"
		:class="{ 'pointer-events-none opacity-50': !show, 'sm:h-[75vh]': !isInThread }"
		:style="isMobile && { height: editorHeight }"
		@change="
			(val: string) => (mail.html_body = val.replaceAll('<div></div>', '<div><br></div>'))
		"
		@dragenter.prevent="handleDragEnter"
		@dragover.prevent="handleDragOver"
		@dragleave.prevent="handleDragLeave"
		@drop.prevent="handleDrop"
	>
		<template #top>
			<div
				class="flex flex-col gap-2.5 border-b pb-2.5 max-sm:px-3 max-sm:pt-2.5"
				:class="{ 'border-transparent': isDragging }"
			>
				<div v-if="!mailDetails?.type || isMobile" class="flex justify-between gap-2">
					<div class="flex items-center gap-2">
						<span class="text-ink-gray-4 text-sm">{{ __('From') }}</span>
						<Combobox
							v-model="mail.from_email"
							:options="
								identities.data.map((i: Identity) => ({
									label: `${i._name} <${i.email}>`,
									value: i.email,
								})) || []
							"
							:open-on-click="true"
							class="min-w-64"
						/>
					</div>
					<Button
						v-if="isInThread"
						variant="ghost"
						:disabled="isLoading || isDraftUpdated"
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
						<div class="flex gap-2">
							<span class="text-ink-gray-4 text-sm leading-7"> {{ __('To') }} </span>
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
									v-if="!(mail.cc?.length || mail.bcc?.length)"
									variant="ghost"
									@click="toggleCcBcc"
								>
									<template #icon>
										<component
											:is="showCcBcc ? ChevronUp : ChevronDown"
											class="text-ink-gray-5 h-4 w-4"
										/>
									</template>
								</Button>
							</div>
						</div>
						<template v-if="showCcBcc">
							<div class="flex gap-2">
								<span class="text-ink-gray-4 text-sm leading-7">
									{{ __('Cc') }}
								</span>
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
							<div class="flex gap-2">
								<span class="text-ink-gray-4 text-sm leading-7">
									{{ __('Bcc') }}
								</span>
								<MultiselectInputControl
									v-model="mail.bcc"
									class="flex-1 text-sm"
									:validate="validateEmail"
									:error-message="
										(value: string) =>
											__(`'{0}' is an invalid email address`, [value])
									"
								/>
							</div>
						</template>
					</div>
				</div>
				<div v-if="!mailDetails?.type || isMobile" class="flex items-center gap-2">
					<span class="text-ink-gray-4 text-sm">{{ __('Subject') }}</span>
					<input
						v-model="mail.subject"
						class="flex-1 border-none bg-inherit text-base focus-visible:!ring-0"
					/>
				</div>
			</div>
		</template>
		<template #editor="{ editor }">
			<div
				class="relative flex flex-1 cursor-text flex-col border-2 border-transparent py-2.5 text-sm max-sm:px-3 sm:overflow-y-auto"
				:class="{
					'max-h-96 min-h-32': isInThread,
					'!border-outline-gray-3 rounded border-dashed': isDragging,
				}"
				@click="editor.commands.focus('end')"
			>
				<div
					v-if="isDragging"
					class="bg-surface-gray-1/90 text-ink-gray-3 absolute inset-0 z-50 flex flex-col items-center justify-center space-y-1 rounded"
				>
					<UploadCloud class="stroke-1.5 h-12 w-12" />
					<p class="text-lg font-semibold">{{ __('Drop files to upload') }}</p>
				</div>

				<EditorContent :editor :class="{ 'opacity-30': isDragging }" @click.stop />

				<div
					class="mt-auto cursor-default space-y-2.5 pt-2.5"
					:class="{ 'opacity-30': isDragging }"
					@click.stop
				>
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

					<div
						v-for="(fileUpload, id) in fileUploads.filter((fu) => fu.isUploading)"
						:key="id"
						class="bg-surface-gray-2 text-ink-gray-6 mb-2 rounded p-2.5 text-sm"
					>
						<div class="mb-1.5 flex items-center">
							<span class="mr-1 font-medium"> {{ fileUpload.name }} </span>
							<span class="font-extralight">
								({{ formatBytes(fileUpload.size) }})
							</span>
						</div>
						<Progress :value="fileUpload.progress" />
					</div>
				</div>
			</div>
		</template>
		<template #bottom>
			<ComposeMailToolbar
				:is-saving-draft
				:is-recipients-empty
				class="border-t"
				:class="{ 'border-transparent': isDragging }"
				@select-files="(files: File[]) => uploadFiles(files)"
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
	watch,
} from 'vue'
import { EditorContent } from '@tiptap/vue-3'
import { watchDebounced } from '@vueuse/core'
import {
	ChevronDown,
	ChevronUp,
	ExternalLink,
	Forward,
	Reply,
	ReplyAll,
	UploadCloud,
} from 'lucide-vue-next'
import {
	Button,
	Combobox,
	Dropdown,
	FeatherIcon,
	ImageExtension,
	Progress,
	TextEditor,
	createResource,
	useFileUpload,
} from 'frappe-ui'

import { formatBytes, isOverlayPresent, raiseToast, validateEmail } from '@/utils'
import { useScreenSize, useVisualViewport } from '@/utils/composables'
import { CustomParagraphExtension } from '@/utils/text-editor'
import { userStore } from '@/stores/user'
import ComposeMailToolbar from '@/components/ComposeMailToolbar.vue'
import MultiselectInputControl from '@/components/Controls/MultiselectInputControl.vue'

import type { Attachment, ComposeMailData, File as FileDoc, Identity, UserResource } from '@/types'

const show = defineModel<boolean>()

const {
	reloadMails,
	mailDetails,
	isInThread = false,
} = defineProps<{
	reloadMails: () => void
	mailDetails?: ComposeMailData
	isInThread?: boolean
}>()

const emit = defineEmits(['discardMail', 'reply', 'replyAll', 'forward', 'popOut'])

const { identities } = userStore()

const getIdentity = (email: string) =>
	identities.data?.find((identity: Identity) => identity.email === email)

// Editor

const { isMobile } = useScreenSize()

const textEditor = useTemplateRef('textEditor')
const toInput = useTemplateRef('toInput')
const ccInput = useTemplateRef('ccInput')

const showCcBcc = ref(!!mailDetails?.cc?.length || !!mailDetails?.bcc?.length)
const toggleCcBcc = () => {
	showCcBcc.value = !showCcBcc.value
	if (showCcBcc.value) nextTick(() => ccInput.value?.setFocus())
}

const appendEmoji = (emoji: string) => {
	textEditor.value.editor.commands.insertContent(emoji)
	textEditor.value.editor.commands.focus()
}

const editorHeight = useVisualViewport(
	(viewport) => `${viewport.height - viewport.offsetTop - 113}px`,
)

// Setup & hooks

const user = inject('$user') as UserResource

const mail = reactive<ComposeMailData>({
	name: mailDetails?.name || '',
	id: mailDetails?.id || '',
	from_email: mailDetails?.from_email || user.data.jmap_default_outgoing_email || user.data.name,
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
	if (!mailDetails?.in_reply_to) setTimeout(() => toInput.value?.setFocus(), 50)
	else textEditor.value.editor.commands.focus()
})

onUnmounted(() => saveDraft())

watchDebounced(mail, () => saveDraft(), { debounce: 2000 })

// Actions

const isSavingDraft = ref(false)

const saveDraft = async () => {
	if (!isDraftUpdated.value || isLoading.value || isDiscarding.value) return

	isSavingDraft.value = true
	if (mail.id) await updateDraft.submit({ submit: false })
	else if (!isMailEmpty.value) await createMail.submit({ save_as_draft: true })
	isSavingDraft.value = false
}

const sendMail = async () => {
	if (deleteMail.loading) return

	if (isRecipientsEmpty.value)
		return raiseToast(__('Please add at least one recipient.'), 'error')

	isSavingDraft.value = false
	show.value = false
	if (createMail.loading) await createMail.promise
	if (updateDraft.loading) await updateDraft.promise

	if (mail.id) updateDraft.submit({ submit: true })
	else createMail.submit({ save_as_draft: false })
}

const isDiscarding = ref(false)

const discardMail = async () => {
	if (deleteMail.loading) return

	isDiscarding.value = true
	show.value = false
	if (createMail.loading) await createMail.promise
	if (updateDraft.loading) await updateDraft.promise
	if (mail.id) deleteMail.submit()
	else emit('discardMail')
}

watch(show, (val) => {
	if (val) return
	isDiscarding.value = false
	isSavingDraft.value = false
})

defineExpose({ sendMail, discardMail })

const onMailUpdateSuccess = ({
	id,
	status,
	error,
}: {
	id: string
	status: string
	error: string
}) => {
	if (id) mail.id = id
	updateOriginalMail()
	if (error) return raiseToast(error, 'error')
	if (isDiscarding.value) return

	if (!isInThread || status === 'Submitted') reloadMails()
	if (show.value) return

	if (status === 'Drafted' && isSavingDraft.value) raiseToast(__('Draft saved.'))
	else if (status === 'Submitted') raiseToast(__('Message sent.'))
}

// Resources

const createMail = createResource({
	url: 'mail.api.mail.create_mail',
	makeParams: ({ save_as_draft }: { save_as_draft: boolean }) => ({
		...mail,
		from_name: getIdentity(mail.from_email!)._name,
		html_body: mail.html_body! + mail.quoted_content,
		save_as_draft,
	}),
	onSuccess: onMailUpdateSuccess,
	onError: (error) => raiseToast(error.message, 'error'),
})

const updateDraft = createResource({
	url: 'mail.api.mail.update_draft_mail',
	makeParams: ({ submit }: { submit: boolean }) => ({
		...mail,
		from_name: getIdentity(mail.from_email!)._name,
		html_body: mail.html_body! + mail.quoted_content,
		submit,
	}),
	onSuccess: onMailUpdateSuccess,
	onError: (error) => raiseToast(error.message, 'error'),
})

const deleteMail = createResource({
	url: 'mail.api.mail.delete_mail',
	makeParams: () => ({ id: mail.id }),
	onSuccess: () => {
		reloadMails()
		raiseToast(__('Draft discarded.'))
	},
	onError: (error) => raiseToast(error.message, 'error'),
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

const isOnlySignature = computed(() => {
	if (!mail.html_body) return false

	const trimmed = mail.html_body.trim()
	const pattern = /^<div\s+class="frappe_mail_signature">[\s\S]*<\/div>$/
	return pattern.test(trimmed)
})

const isBodyEmpty = computed(() => {
	let isEmpty = true
	if (mail.html_body) {
		const element = document.createElement('div')
		element.innerHTML = mail.html_body
		isEmpty =
			!element.textContent?.trim() &&
			Array.from(element.children).every((d) => !d.textContent?.trim())
	}

	return isEmpty
})

const isMailEmpty = computed(() => {
	const isSubjectEmpty = !mail.subject.length
	const isQuotedContentEmpty = !mail.quoted_content?.length
	const isAttachmentsEmpty = !mail.attachments.length

	return (
		isSubjectEmpty &&
		isQuotedContentEmpty &&
		isRecipientsEmpty.value &&
		isAttachmentsEmpty &&
		(isBodyEmpty.value || isOnlySignature.value)
	)
})

const openQuotedContent = () => {
	mail.html_body += `<br>${mail.quoted_content}`
	mail.quoted_content = ''
}

watch(
	() => mail.from_email,
	(val) => {
		if (isBodyEmpty.value || isOnlySignature.value) {
			const identity = getIdentity(val!)
			mail.html_body = identity?.html_signature
				? `<div class="frappe_mail_signature"><br>${identity.html_signature}</div>`
				: ''
		}
	},
	{ immediate: true },
)

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

// Custom Extensions

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

// Shortcuts

const handleKeydown = (e: KeyboardEvent) => {
	if (!show.value || (isInThread && isOverlayPresent())) return

	handleSendShortcut(e)
	handleDiscardShortcut(e)
}

const handleSendShortcut = (e: KeyboardEvent) => {
	if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
		e.preventDefault()
		sendMail()
	}
}

const handleDiscardShortcut = (e: KeyboardEvent) => {
	if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'd') {
		e.preventDefault()
		discardMail()
	}
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))

// Drag and drop file upload

const isDragging = ref(false)
let dragCounter = 0

const handleDragEnter = (e: DragEvent) => {
	e.preventDefault()
	dragCounter++
	if (e.dataTransfer?.types.includes('Files')) isDragging.value = true
}

const handleDragOver = (e: DragEvent) => {
	e.preventDefault()
	if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
}

const handleDragLeave = (e: DragEvent) => {
	e.preventDefault()
	dragCounter--
	if (dragCounter === 0) isDragging.value = false
}

const handleDrop = (e: DragEvent) => {
	e.preventDefault()
	isDragging.value = false
	dragCounter = 0

	const files = Array.from(e.dataTransfer?.files ?? [])
	uploadFiles(files)
}

const fileUploads = ref<ReturnType<typeof useFileUpload>[]>([])

const uploadFiles = async (files: File[]) => {
	if (!files.length) return

	const results = await Promise.allSettled(files.map(uploadFile))
	results.forEach((res, i) => {
		if (res.status === 'rejected')
			raiseToast(__('Failed to upload {0}', [files[i].name]), 'error')
	})
}

const uploadFile = async (file: File) => {
	const fileUpload = useFileUpload()
	fileUploads.value.push({ name: file.name, size: file.size, ...fileUpload })

	const doc = (await fileUpload.upload(file, {
		private: true,
		folder: 'Home/Frappe Mail',
	})) as FileDoc

	attachDoc(doc)
}

const attachDoc = (doc: FileDoc) =>
	mail.attachments.push({
		file_name: doc.file_name,
		file_url: doc.file_url,
		file_size: doc.file_size,
		disposition: 'attachment',
	})
</script>
