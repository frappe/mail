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
	>
		<template #top>
			<div class="flex flex-col gap-2.5 border-b pb-2.5 max-sm:px-3 max-sm:pt-2.5">
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
							<Tooltip :text="__('Select from contacts')">
								<span
									class="text-ink-gray-4 cursor-pointer text-sm leading-7 hover:underline"
									@click="insertContacts('to')"
								>
									{{ __('To') }}
								</span>
							</Tooltip>
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
								<Tooltip :text="__('Select from contacts')">
									<span
										class="text-ink-gray-4 cursor-pointer text-sm leading-7 hover:underline"
										@click="insertContacts('cc')"
									>
										{{ __('Cc') }}
									</span>
								</Tooltip>
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
								<Tooltip :text="__('Select from contacts')">
									<span
										class="text-ink-gray-4 cursor-pointer text-sm leading-7 hover:underline"
										@click="insertContacts('bcc')"
									>
										{{ __('Bcc') }}
									</span>
								</Tooltip>
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
				class="flex flex-1 cursor-text flex-col py-2.5 text-sm max-sm:px-3 sm:overflow-y-auto"
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

	<ContactsModal
		v-model="showContactsModal"
		@insert="(selections) => mail[insertContactsInto].push(...selections)"
	/>
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
import { ChevronDown, ChevronUp, ExternalLink, Forward, Reply, ReplyAll } from 'lucide-vue-next'
import {
	Button,
	Combobox,
	Dropdown,
	FeatherIcon,
	ImageExtension,
	TextEditor,
	Tooltip,
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

import ContactsModal from './Modals/ContactsModal.vue'

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

const showContactsModal = ref(false)
const insertContactsInto = ref('')

const insertContacts = (insertInto: string) => {
	insertContactsInto.value = insertInto
	showContactsModal.value = true
}

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
	if (!isDraftUpdated.value || isLoading.value) return

	isSavingDraft.value = true
	if (mail.id) await updateDraft.submit()
	else if (!isMailEmpty.value) await createMail.submit()
	isSavingDraft.value = false
}

const sendMail = () => {
	if (isLoading.value) return

	if (isRecipientsEmpty.value) return raiseToast(__('Please add at least one recipient.'))
	show.value = false
	if (mail.id) updateDraft.submit()
	else createMail.submit()
}

const discardMail = () => {
	if (isLoading.value) return

	show.value = false
	if (mail.id) deleteMail.submit()
	else emit('discardMail')
}

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
	if (!isInThread || status === 'Submitted') reloadMails()

	if (show.value) return
	if (status === 'Drafted') raiseToast(__('Draft saved.'))
	else if (status === 'Submitted') raiseToast(__('Message sent.'))
}

// Resources

const createMail = createResource({
	url: 'mail.api.mail.create_mail',
	makeParams: () => ({
		...mail,
		from_name: getIdentity(mail.from_email!)._name,
		html_body: mail.html_body! + mail.quoted_content,
		save_as_draft: isSavingDraft.value,
	}),
	onSuccess: onMailUpdateSuccess,
	onError: (error) => raiseToast(error.message, 'error'),
})

const updateDraft = createResource({
	url: 'mail.api.mail.update_draft_mail',
	makeParams: () => ({
		...mail,
		from_name: getIdentity(mail.from_email!)._name,
		html_body: mail.html_body! + mail.quoted_content,
		submit: !isSavingDraft.value,
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
</script>
