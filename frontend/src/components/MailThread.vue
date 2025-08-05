<template>
	<div v-if="threadID" class="relative flex h-full flex-col overflow-hidden">
		<div class="bg-surface-white sticky top-0 flex items-center border-b p-2.5 sm:px-5">
			<Button
				icon="chevron-left"
				variant="ghost"
				class="mr-2 shrink-0"
				@click="router.push({ name: 'Mailbox', params: { mailbox } })"
			/>
			<span
				v-if="mailThread.loading"
				class="bg-surface-gray-3 h-3.5 animate-pulse"
				:style="{
					width: `${Math.max(100, Math.random() * (isMobile ? 300 : 800))}px`,
				}"
			/>
			<template v-else>
				<h2 v-if="!isMobile" class="mr-2 truncate font-semibold leading-5">
					{{ mailThread?.data?.[0].subject || __('[No subject]') }}
				</h2>
				<div class="ml-auto shrink-0 space-x-2">
					<Tooltip v-if="mailbox !== 'starred'" :text="__('Move To')">
						<Dropdown :options="moveToOptions">
							<Button variant="ghost">
								<template #icon>
									<component :is="FolderInput" class="text-ink-gray-5 h-4 w-4" />
								</template>
							</Button>
						</Dropdown>
					</Tooltip>
					<Tooltip
						v-for="action in threadActions"
						:key="action.label"
						:text="action.label"
					>
						<Button variant="ghost" @click="action.onClick">
							<template #icon>
								<component :is="action.icon" class="text-ink-gray-5 h-4 w-4" />
							</template>
						</Button>
					</Tooltip>
				</div>
			</template>
		</div>
		<div class="flex-1 overflow-y-auto">
			<div v-if="isMobile && !mailThread.loading" class="border-b px-3 py-3.5">
				<h2 class="font-semibold leading-5">
					{{ mailThread?.data?.[0].subject || __('[No subject]') }}
				</h2>
			</div>

			<MailThreadPlaceholder v-if="mailThread.loading" />

			<div v-else class="space-y-4 sm:px-5 sm:py-6">
				<div
					v-for="mail in mailThread.data"
					:key="mail.name"
					:class="{
						'p-3.5': isMobile,
						'border-b p-3.5 sm:rounded-md sm:border': mailThread.data.length > 1,
						'cursor-pointer': isCollapsed(mail),
					}"
					@click="mail.collapsed = false"
				>
					<div
						class="flex space-x-3"
						:class="{
							'cursor-pointer': mail !== mailThread.data[mailThread.data.length - 1],
							'pb-6': mail.preview,
						}"
						@click.stop="mail.collapsed = !mail.collapsed"
					>
						<Avatar
							:label="
								getFirstAlphabet(mail.from_name) ||
								getFirstAlphabet(mail.from_email)
							"
							:image="mail.user_image"
							size="xl"
						/>
						<div class="flex flex-1 justify-between truncate text-sm">
							<div class="mr-3 flex flex-col space-y-1 truncate">
								<div class="flex items-center space-x-1.5">
									<span class="text-base font-semibold">
										{{ mail.from_name || mail.from_email }}
									</span>
									<span
										v-if="mail.from_name && !isMobile"
										class="text-ink-gray-5"
									>
										{{ `<${mail.from_email}>` }}
									</span>
									<MailDetailsPopover
										v-if="!(mail.draft || isCollapsed(mail))"
										:mail="mail"
									/>
								</div>
								<div class="truncate">{{ getAllRecipients(mail) }}</div>
							</div>
							<div class="flex items-center space-x-1 self-start">
								<MailDate :datetime="mail.received_at" />
								<Tooltip
									v-if="mail.flagged && mailbox !== 'trash'"
									:text="__('Unstar')"
								>
									<Button
										variant="ghost"
										@click.stop="
											starMails.submit({
												names: [mail.name],
												flagged: false,
											})
										"
									>
										<template #icon>
											<Star
												class="fill-ink-amber-2 text-ink-amber-2 h-4 w-4"
											/>
										</template>
									</Button>
								</Tooltip>
								<Tooltip
									v-for="action in mailActions(mail).filter(
										(d) => d.condition !== false && !isCollapsed(mail),
									)"
									:key="action.label"
									:text="action.label"
								>
									<Button variant="ghost" @click.stop="action.onClick">
										<template #icon>
											<component
												:is="action.icon"
												class="text-ink-gray-5 h-4 w-4"
											/>
										</template>
									</Button>
								</Tooltip>
								<Tooltip v-if="!isCollapsed(mail)" :text="__('More')">
									<Dropdown
										:options="
											moreActions(mail).filter((d) => d.condition !== false)
										"
									>
										<span @click.stop>
											<Button variant="ghost">
												<template #icon>
													<Ellipsis class="text-ink-gray-5 h-4 w-4" />
												</template>
											</Button>
										</span>
									</Dropdown>
								</Tooltip>
							</div>
						</div>
					</div>

					<div v-show="isCollapsed(mail)" class="truncate">{{ mail.preview }}</div>

					<div v-show="!isCollapsed(mail)">
						<EmailContent v-if="mail.html_body" :content="mail.html_body" />
						<pre v-else-if="mail.text_body" class="text-wrap pt-4 text-sm leading-5">{{
							mail.text_body
						}}</pre>

						<div v-if="mail.attachments?.length" class="mt-8 flex flex-wrap space-x-2">
							<AttachmentCapsule
								v-for="attachment in mail.attachments"
								:key="attachment.name"
								:file-name="attachment.filename"
								:blob-i-d="attachment.blob_id"
								:type="attachment.type"
								class="mb-2"
							/>
						</div>
					</div>
				</div>
			</div>
		</div>
		<SendMail
			v-model="showSendModal"
			:mail-i-d="draftMailID"
			:mail-details
			@reload-mails="emit('reloadMails')"
		/>
	</div>

	<div v-else class="h-full overflow-hidden">
		<div
			class="bg-surface-gray-1 m-5 flex h-[calc(100%-2.9em)] items-center justify-center rounded-md"
		>
			<div class="flex flex-col items-center space-y-3">
				<NoMails class="text-ink-gray-2 h-16 w-16" />
				<p class="text-ink-gray-4">
					{{ __('Select an email to view the thread.') }}
				</p>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
	Code,
	Ellipsis,
	ExternalLink,
	FolderInput,
	Forward,
	Mail as MailIcon,
	Reply,
	ReplyAll,
	SquarePen,
	Star,
	Trash2,
} from 'lucide-vue-next'
import { Avatar, Button, Dropdown, Tooltip, createResource } from 'frappe-ui'

import { getFirstAlphabet, getRecipients } from '@/utils'
import { useScreenSize } from '@/utils/composables'
import AttachmentCapsule from '@/components/AttachmentCapsule.vue'
import EmailContent from '@/components/EmailContent.vue'
import NoMails from '@/components/Icons/NoMails.vue'
import MailDate from '@/components/MailDate.vue'
import MailDetailsPopover from '@/components/MailDetailsPopover.vue'
import MailThreadPlaceholder from '@/components/MailThreadPlaceholder.vue'
import SendMail from '@/components/SendMail.vue'

import type { ComposeMailData, Mail } from '@/types'

const { mailbox, threadID } = defineProps<{ mailbox: string; threadID?: string }>()

const emit = defineEmits(['reloadMails', 'setSeen', 'moveThread', 'deleteThread'])

const { isMobile } = useScreenSize()
const dayjs = inject('$dayjs')
const router = useRouter()

const showSendModal = ref(false)
const draftMailID = ref<string>()

const mailDetails = reactive<ComposeMailData>({
	from_email: '',
	to: [],
	cc: [],
	bcc: [],
	subject: '',
	html_body: '',
	attachments: [],
	in_reply_to: '',
	in_reply_to_id: '',
})

const mailThread = createResource({
	url: 'mail.api.mail.get_mail_thread',
	auto: !!threadID,
	makeParams: () => ({ thread_id: threadID }),
	transform: (data: Mail[]) =>
		data
			.filter((mail) =>
				mailbox === 'trash'
					? mail.mailbox_role === 'trash'
					: mail.mailbox_role !== 'trash',
			)
			.map((mail) => ({
				...mail,
				collapsed: !!mail.seen,
			})),
	onSuccess: (data: Mail[]) => {
		if (data.some((mail) => !mail.seen)) emit('setSeen', true)
	},
	onError: () => router.push({ name: 'Mailbox', params: { mailbox } }),
})

const reload = () => {
	if (threadID) mailThread.reload()
}

defineExpose({ reload })

const user = inject('$user')

const moveToOptions = computed(() =>
	user.data.mailboxes
		.filter((m) => ![mailbox, 'sent', 'drafts'].includes(m.role))
		.map((m) => ({
			label: m.name,
			onClick: () => emit('moveThread', m.role),
		})),
)

interface MailAction {
	label: string
	onClick: () => void
	icon: typeof SquarePen
	condition?: boolean | (() => boolean)
}

const threadActions = computed((): MailAction[] =>
	[
		{
			label: __('Mark as Unread'),
			onClick: () => emit('setSeen', false),
			icon: MailIcon,
		},
		{
			label: __('Move to Trash'),
			onClick: () => emit('moveThread', 'trash'),
			icon: Trash2,
			condition: mailbox !== 'trash',
		},
		{
			label: __('Delete Thread'),
			onClick: () => emit('deleteThread'),
			icon: Trash2,
			condition: mailbox === 'trash',
		},
	].filter((action) => action.condition !== false),
)

const mailActions = (mail: Mail): MailAction[] => [
	{
		label: __('Star'),
		onClick: () => starMails.submit({ names: [mail.name], flagged: true }),
		icon: Star,
		condition: !mail.flagged && mailbox !== 'trash',
	},
	{
		label: __('Edit Draft'),
		onClick: () => editDraft(mail),
		icon: SquarePen,
		condition: !!mail.draft,
	},
	{
		label: __('Reply'),
		onClick: () => reply(mail),
		icon: Reply,
		condition: !mail.draft,
	},
]

const moreActions = (mail: Mail): MailAction[] => [
	{
		label: __('Reply All'),
		onClick: () => replyAll(mail),
		icon: ReplyAll,
		condition: () =>
			!mail.draft &&
			mail.from_email !== user.data.email &&
			mail.recipients.To?.concat(mail.recipients.Cc || []).filter(
				(m) => m.email !== user.data.email,
			).length > 0,
	},
	{
		label: __('Forward'),
		onClick: () => forward(mail),
		icon: Forward,
		condition: () => !mail.draft,
	},
	{
		label: __('Move to Trash'),
		onClick: () => moveMail.submit({ mail_ids: [mail.name], mailbox: 'trash' }),
		icon: Trash2,
		condition: () => mailbox !== 'trash',
	},
	{
		label: __('Delete Message'),
		onClick: () => deleteMails.submit([mail.name]),
		icon: Trash2,
		condition: () => mailbox === 'trash',
	},
	{
		label: __('See MIME Message'),
		onClick: () => window.open(`/mail/mime-message/${mail.name}`, '_blank')?.focus(),
		icon: Code,
		condition: () => !mail.draft && !isMobile.value,
	},
	{
		label: __('View in Desk'),
		onClick: () => window.open(`/app/email-message/${mail.name}`, '_blank')?.focus(),
		icon: ExternalLink,
		condition: () => user.data.is_system_manager,
	},
]

const isCollapsed = (mail: Mail) =>
	mail.collapsed && mail !== mailThread.data[mailThread.data.length - 1]

const getAllRecipients = (mail: Mail) => {
	let recipients = ''
	if (mail.recipients.To?.length)
		recipients += __('To: ') + getRecipients(mail.recipients.To) + ' '
	if (mail.recipients.Cc?.length)
		recipients += __('Cc: ') + getRecipients(mail.recipients.Cc) + ' '
	if (mail.recipients.Bcc?.length)
		recipients += __('Bcc: ') + getRecipients(mail.recipients.Bcc) + ' '
	return recipients
}

const moveMail = createResource({
	url: 'mail.api.mail.set_mails_mailbox',
	makeParams: ({ mail_ids, mailbox }: { mail_ids: string[]; mailbox: string }) => ({
		mail_ids,
		mailbox,
	}),
	onSuccess: () => emit('reloadMails'),
})

const deleteMails = createResource({
	url: 'mail.mail.doctype.email_message.email_message.bulk_destroy',
	makeParams: (names: string[]) => ({ names }),
	onSuccess: () => emit('reloadMails'),
})

const starMails = createResource({
	url: 'mail.api.mail.set_flagged',
	makeParams: ({ names, flagged }: { names: string[]; flagged: boolean }) => ({
		names,
		flagged,
	}),
	onSuccess: ({ names, flagged }) =>
		names.forEach(
			(name) =>
				(mailThread.data.find((m: Mail) => m.name === name).flagged = Number(flagged)),
		),
})

const editDraft = (mail: Mail) => {
	draftMailID.value = mail.name
	mailDetails.from_email = mail.from_email
	mailDetails.to = mail.recipients.To?.map((m) => m.email) || []
	mailDetails.cc = mail.recipients.Cc?.map((m) => m.email) || []
	mailDetails.bcc = mail.recipients.Bcc?.map((m) => m.email) || []
	mailDetails.subject = mail.subject || ''
	mailDetails.html_body = mail.html_body
	mailDetails.attachments = mail.attachments || []
	showSendModal.value = true
}

const reply = (mail: Mail) => {
	if (isUserEmail(mail.from_email))
		mailDetails.to = mail.recipients.To?.map((rcpt) => rcpt.email)
	else mailDetails.to = mail.reply_to.length ? mail.reply_to : [mail.from_email]

	setReplyDetailsAndOpenModal(mail)
}

const replyAll = (mail: Mail) => {
	if (isUserEmail(mail.from_email)) {
		mailDetails.to = mail.recipients.To?.map((rcpt) => rcpt.email) || []
		mailDetails.cc = mail.recipients.Cc?.map((rcpt) => rcpt.email) || []
	} else {
		mailDetails.to = mail.reply_to.length ? mail.reply_to : [mail.from_email]

		const originalRecipients = [...(mail.recipients.To || []), ...(mail.recipients.Cc || [])]
		mailDetails.cc = originalRecipients
			.filter((rcpt) => !isUserEmail(rcpt.email))
			.map((rcpt) => rcpt.email)
	}

	setReplyDetailsAndOpenModal(mail)
}

const forward = (mail: Mail) => {
	mailDetails.subject = `Fwd: ${mail.subject}`
	mailDetails.html_body = getMailBody(mail)
	showSendModal.value = true
}

const isUserEmail = (email: string) => user.data.email_addresses.includes(email)

const setReplyDetailsAndOpenModal = (mail: Mail) => {
	mailDetails.subject = mail.subject.startsWith('Re: ') ? mail.subject : `Re: ${mail.subject}`
	mailDetails.html_body = getMailBody(mail)
	mailDetails.in_reply_to = mail.message_id
	mailDetails.in_reply_to_id = mail._id
	showSendModal.value = true
}

const getMailBody = (mail: Mail) => {
	if (!mail.html_body) return ''
	const replyHeader = `On ${dayjs(mail.received_at).format('DD MMM YYYY')} at ${dayjs(mail.received_at).format('h:mm A')}, ${mail.from_email} wrote:`
	return `<div class="frappe_mail_quote">${replyHeader}<br><blockquote style="margin-left: 8px"><br>${mail.html_body}</blockquote></div>`
}

watch(() => threadID, reload)
</script>
