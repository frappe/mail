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
				v-if="thread.loading"
				class="bg-surface-gray-3 h-3.5 animate-pulse"
				:style="{
					width: `${Math.max(100, Math.random() * (isMobile ? 300 : 800))}px`,
				}"
			/>
			<template v-else>
				<h2 v-if="!isMobile" class="mr-2 truncate font-semibold leading-5">
					{{ thread?.data?.[0]?.subject || __('[No subject]') }}
				</h2>
				<div class="ml-auto shrink-0 space-x-2">
					<Tooltip v-if="mailbox !== 'starred'" :text="__('Move To')">
						<Dropdown :options="moveToOptions">
							<Button variant="ghost">
								<template #icon>
									<FolderInput class="text-ink-gray-5 h-4 w-4" />
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
			<div v-if="isMobile && !thread.loading" class="border-b px-3 py-3.5">
				<h2 class="font-semibold leading-5">
					{{ thread?.data?.[0].subject || __('[No subject]') }}
				</h2>
			</div>

			<MailThreadPlaceholder v-if="thread.loading" />

			<div v-else class="space-y-4 sm:px-5 sm:py-6">
				<div
					v-for="mail in thread.data"
					:key="mail.name"
					:class="{
						'p-3.5': isMobile,
						'border-b p-3.5 sm:rounded-md sm:border':
							thread.data.length > 1 || mail.draft,
						'cursor-pointer': isCollapsed(mail),
					}"
					@click="mail.collapsed = false"
				>
					<ComposeMailEditor
						v-if="mail.draft"
						:mail-i-d="mail._id"
						:mail-details="draftMails[mail.name]"
						:is-in-thread="true"
						@reload-mails="emit('reloadMails')"
						@discard-mail="discardDraft(mail.name)"
						@reply="reply(getSourceMail(mail.name))"
						@reply-all="replyAll(getSourceMail(mail.name))"
						@forward="forward(getSourceMail(mail.name))"
					/>

					<template v-else>
						<div
							class="flex space-x-3"
							:class="{
								'cursor-pointer': mail !== thread.data[thread.data.length - 1],
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
										<MailDetailsPopover v-if="!isCollapsed(mail)" :mail />
									</div>
									<div class="truncate">
										{{ getFormattedRecipients(mail.recipients) }}
									</div>
								</div>
								<div class="flex items-center space-x-1 self-start">
									<MailDate :datetime="mail.received_at" />
									<Tooltip
										v-if="mail.flagged && mailbox !== mailboxIds.trash"
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
												moreActions(mail).filter(
													(d) => d.condition !== false,
												)
											"
										>
											<span @click.stop>
												<Button variant="ghost">
													<template #icon>
														<Ellipsis
															class="text-ink-gray-5 h-4 w-4"
														/>
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
							<pre
								v-else-if="mail.text_body"
								class="text-wrap pt-4 text-sm leading-5"
								>{{ mail.text_body }}</pre
							>

							<div
								v-if="mail.attachments?.length"
								class="mt-8 flex flex-wrap space-x-2"
							>
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
					</template>
				</div>

				<div v-if="!thread.data?.at(-1)?.draft" class="flex items-center space-x-2">
					<Button
						:icon-left="Reply"
						:label="__('Reply')"
						variant="outline"
						@click="reply(thread.data.at(-1))"
					/>
					<Button
						:icon-left="Forward"
						:label="__('Forward')"
						variant="outline"
						@click="forward(thread.data.at(-1))"
					/>
				</div>
			</div>
		</div>
		<SendMail
			v-if="draftMailID"
			v-model="showSendModal"
			:mail-i-d="draftMailID"
			:mail-details="draftMails[draftMailID]"
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
import { computed, inject, nextTick, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
	ArrowUpRight,
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

import {
	extractQuotedContent,
	getFirstAlphabet,
	getFormattedRecipients,
	getGroupedRecipients,
} from '@/utils'
import { useScreenSize } from '@/utils/composables'
import { userStore } from '@/stores/user'
import AttachmentCapsule from '@/components/AttachmentCapsule.vue'
import ComposeMailEditor from '@/components/ComposeMailEditor.vue'
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
const { mailboxes, mailboxIds } = userStore()

const showSendModal = ref(false)
const draftMailID = ref<string>()

const draftMails = reactive<{ [key: string]: ComposeMailData }>({})

const thread = createResource({
	url: 'mail.api.mail.get_thread',
	auto: !!threadID,
	makeParams: () => ({ thread_id: threadID }),
	transform: (data: Mail[]) =>
		data
			.filter((mail) => {
				const mailboxes = mail.mailboxes.map((m) => m.mailbox_id)
				const trash = mailboxIds.trash
				return mailbox === trash ? mailboxes.includes(trash) : !mailboxes.includes(trash)
			})
			.map((mail) => ({
				...mail,
				groupedRecipients: getGroupedRecipients(mail.recipients, false),
				collapsed: !!mail.seen,
			})),
	onSuccess: (data: Mail[]) => {
		if (!data.length) return router.push({ name: 'Mailbox', params: { mailbox } })
		let unseen = true
		data.forEach((mail) => {
			if (unseen && !mail.seen) {
				emit('setSeen', true)
				unseen = false
			}
			if (mail.draft) {
				mail.groupedRecipients = getGroupedRecipients(mail.recipients, false) as {
					to: string[]
					cc: string[]
					bcc: string[]
				}
				populateDraftMails(mail)
			}
		})
	},
	onError: () => router.push({ name: 'Mailbox', params: { mailbox } }),
})

const reload = () => {
	if (threadID) thread.reload()
}

watch(() => threadID, reload)

defineExpose({ reload })

const user = inject('$user')

const moveToOptions = computed(() =>
	mailboxes.data
		?.filter((m) => ![mailbox, mailboxIds.sent, mailboxIds.drafts].includes(m.id))
		.map((m) => ({ label: m._name, onClick: () => emit('moveThread', m.id) })),
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
			onClick: () => emit('moveThread', mailboxIds.trash),
			icon: Trash2,
			condition: mailbox !== mailboxIds.trash,
		},
		{
			label: __('Delete Thread'),
			onClick: () => emit('deleteThread'),
			icon: Trash2,
			condition: mailbox === mailboxIds.trash,
		},
	].filter((action) => action.condition !== false),
)

const mailActions = (mail: Mail): MailAction[] => [
	{
		label: __('Star'),
		onClick: () => starMails.submit({ _ids: [mail._id], flagged: true }),
		icon: Star,
		condition: !mail.flagged && mailbox !== mailboxIds.trash,
	},
	{
		label: __('Pop Out'),
		onClick: () => editDraft(mail),
		icon: ArrowUpRight,
		condition: !!mail.draft && !isMobile.value,
	},
	{
		label: __('Edit Draft'),
		onClick: () => editDraft(mail),
		icon: SquarePen,
		condition: !!mail.draft && isMobile.value,
	},
	{
		label: __('Reply'),
		onClick: () => reply(mail),
		icon: Reply,
		condition: !mail.draft,
	},
]

interface GroupedAction {
	group: string
	items: MailAction[]
}

const moreActions = (mail: Mail): GroupedAction[] => [
	{
		group: '',
		items: [
			{
				label: __('Reply All'),
				onClick: () => replyAll(mail),
				icon: ReplyAll,
				condition: () =>
					!mail.draft &&
					mail.from_email !== user.data.email &&
					mail.groupedRecipients.to
						?.concat(mail.groupedRecipients.cc)
						.filter((m) => m !== user.data.email).length > 0,
			},
			{
				label: __('Forward'),
				onClick: () => forward(mail),
				icon: Forward,
				condition: () => !mail.draft,
			},
			{
				label: __('Move to Trash'),
				onClick: () => moveMail.submit({ _ids: [mail._id], mailbox: mailboxIds.trash }),
				icon: Trash2,
				condition: () => mailbox !== mailboxIds.trash,
			},
			{
				label: __('Delete Message'),
				onClick: () => deleteMails.submit([mail.name]),
				icon: Trash2,
				condition: () => mailbox === mailboxIds.trash,
			},
		],
	},
	{
		group: '',
		items: [
			{
				label: __('See MIME Message'),
				onClick: () => window.open(`/mail/mime-message/${mail.name}`, '_blank')?.focus(),
				icon: Code,
				condition: () => !mail.draft && !isMobile.value,
			},
			{
				label: __('View in Desk'),
				onClick: () => window.open(`/app/mail-message/${mail.name}`, '_blank')?.focus(),
				icon: ExternalLink,
				condition: () => user.data.is_system_manager,
			},
		],
	},
]

const isCollapsed = (mail: Mail) => mail.collapsed && mail !== thread.data[thread.data.length - 1]

const moveMail = createResource({
	url: 'mail.api.mail.move_mails',
	makeParams: ({ _ids, mailbox }: { _ids: string[]; mailbox: string }) => ({ _ids, mailbox }),
	onSuccess: () => emit('reloadMails'),
})

const deleteMails = createResource({
	url: 'mail.mail.doctype.mail_message.mail_message.bulk_delete',
	makeParams: (names: string[]) => ({ names }),
	onSuccess: () => {
		if (thread.data.length == 1) router.push({ name: 'Mailbox', params: { mailbox } })
		emit('reloadMails')
	},
})

const starMails = createResource({
	url: 'mail.api.mail.set_flagged',
	makeParams: ({ _ids, flagged }: { _ids: string[]; flagged: boolean }) => ({
		_ids,
		flagged,
	}),
	onSuccess: ({ _ids, flagged }: { _ids: string[]; flagged: boolean }) =>
		_ids.forEach(
			(_id) => (thread.data.find((m: Mail) => m._id === _id).flagged = Number(flagged)),
		),
})

const populateDraftMails = (mail: Mail) =>
	(draftMails[mail.name] = {
		name: mail.name,
		from_email: mail.from_email,
		to: mail.groupedRecipients.to,
		cc: mail.groupedRecipients.cc,
		bcc: mail.groupedRecipients.bcc,
		subject: mail.subject || '',
		in_reply_to: mail.message_id,
		in_reply_to_id: mail._id,
		attachments: mail.attachments || [],
		...extractQuotedContent(mail.html_body),
	})

const reply = (mail: Mail) =>
	createDraft(mail, {
		...getReplyDetails(mail),
		...getReplyRecipients(mail),
		type: 'reply',
	})

const replyAll = (mail: Mail) =>
	createDraft(mail, {
		...getReplyDetails(mail),
		...getReplyAllRecipients(mail),
		type: 'replyAll',
	})

const forward = (mail: Mail) =>
	createDraft(mail, {
		subject: `Fwd: ${mail.subject}`,
		html_body: getForwardedContent(mail),
		type: 'forward',
	})

const createDraft = (mail: Mail, draftDetails: ComposeMailData) => {
	mail.collapsed = false
	const name = `draft:${mail.name}`
	if (name in draftMails) discardDraft(name)

	nextTick(() => {
		draftMails[name] = { name, ...draftDetails }
		const index = thread.data.indexOf(mail)
		const draft = thread.data.find((m: Mail) => m.name === name)
		if (index !== -1 && !draft)
			thread.data.splice(index + 1, 0, { ...draftMails[name], draft: 1 })
	})
}

const getSourceMail = (mail: string) =>
	thread.data.find((m: Mail) => m.name === mail.split(':')[1])

const discardDraft = (mail: string) => {
	delete draftMails[mail]
	thread.data = thread.data.filter((m: Mail) => m.name !== mail)
}

const getReplyDetails = (mail: Mail) => ({
	subject: mail.subject?.startsWith('Re: ') ? mail.subject : `Re: ${mail.subject}`,
	quoted_content: getQuotedContent(mail),
	in_reply_to: mail.message_id,
	in_reply_to_id: mail._id,
})

const getReplyRecipients = (mail: Mail) => ({
	to: isUserEmail(mail.from_email)
		? mail.groupedRecipients.to
		: mail.reply_to.length
			? mail.reply_to.map((r) => r.email)
			: [mail.from_email],
})

const getReplyAllRecipients = (mail: Mail) => {
	if (isUserEmail(mail.from_email))
		return { to: mail.groupedRecipients.to, cc: mail.groupedRecipients.cc }
	else
		return {
			to: mail.reply_to.length ? mail.reply_to.map((r) => r.email) : [mail.from_email],
			cc: [...mail.groupedRecipients.to, ...mail.groupedRecipients.cc].filter(
				(r) => !isUserEmail(r),
			),
		}
}

const isUserEmail = (email: string) => user.data.email_addresses.includes(email)

const getQuotedContent = (mail: Mail) =>
	`
		<div class="frappe_mail_quote">
			On ${dayjs(mail.received_at).format('DD MMM YYYY [at] h:mm A')}, ${mail.from_email} wrote:
			<blockquote style="margin-left: 8px">
				${mail.html_body || '&nbsp;'}
			</blockquote>
		</div>
	`

const getForwardedContent = (mail: Mail) =>
	`
		---------- Forwarded message --------- <br>
		From: ${mail.from_name} <${mail.from_email}> <br>
		Date: ${dayjs(mail.received_at).format('ddd, MMM D, YYYY [at] h:mm A')} <br>
		Subject: ${mail.subject || ''} <br>
		To: ${mail.groupedRecipients.to.join(', ')} <br>
		${mail.groupedRecipients.cc.length ? `Cc: ${mail.groupedRecipients.cc.join(', ')} <br>` : ''}
		<br><br>
		${mail.html_body || '&nbsp;'}
	`
</script>
