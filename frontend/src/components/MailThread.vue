<template>
	<div v-if="threadID" class="relative flex h-full flex-col overflow-hidden">
		<ThreadHeader
			:threads
			:thread
			@set-flagged="(ids: string[], flagged: boolean) => emit('setFlagged', ids, flagged)"
			@set-seen="(seen: boolean) => emit('setSeen', seen)"
			@move-thread="(moveToMailbox: string) => emit('moveThread', moveToMailbox)"
			@set-spam-status="(spam: boolean) => emit('setSpamStatus', spam)"
			@delete-thread="() => emit('deleteThread')"
			@prev-thread="() => emit('prevThread')"
			@next-thread="() => emit('nextThread')"
		/>
		<div ref="threadContainer" class="flex-1 overflow-y-auto">
			<div v-if="isMobile && !thread.loading" class="border-b px-3 py-3.5">
				<h2 class="text-lg font-semibold leading-5">
					{{ thread?.data?.[0].subject || __('[No subject]') }}
				</h2>
			</div>

			<MailThreadPlaceholder v-if="thread.loading" />

			<div
				v-else
				class="sm:space-y-4 sm:px-5 sm:py-6"
				:class="{ 'pb-16': isMobile && !thread.data?.at(-1)?.draft }"
			>
				<template v-for="group in mailsByDay" :key="group.date">
					<div
						v-if="
							!isMobile &&
							mailsByDay.length > 1 &&
							user.data.group_messages_by === 'Day'
						"
						class="flex items-center px-1"
					>
						<div class="border-outline-gray-1 flex-1 border-t" />
						<span class="text-ink-gray-5 rounded-full border px-2 py-1 text-xs">
							{{ getFormattedDate(group.date || dayjs()) }}
						</span>
						<div class="border-outline-gray-1 flex-1 border-t" />
					</div>
					<template v-for="mail in group.mails" :key="mail.name">
						<div
							v-if="shouldShowMarker(mail.id)"
							ref="unseenMarker"
							class="flex items-center gap-3 px-1"
						>
							<div class="bg-surface-blue-3 h-px flex-1" />
							<span class="text-ink-blue-3 text-xs">
								{{
									__('{0} new {1}', [
										unseenCount,
										unseenCount === 1 ? __('mail') : __('mails'),
									])
								}}
							</span>
							<div class="bg-surface-blue-3 h-px flex-1" />
						</div>
						<div
							ref="mails"
							:data-mail-name="mail.name"
							:class="{
								'px-3 py-5': isMobile,
								'max-sm:border-b sm:rounded-xl sm:p-5':
									thread.data.length > 1 || mail.draft,
								'sm:border':
									(thread.data.length > 1 && !mail.draft) ||
									(mail.draft && dataTheme === 'dark'),
								'cursor-pointer': isCollapsed(mail),
								'sm:shadow-elevation-light-md':
									mail.draft && dataTheme === 'light',
							}"
							@click="mail.collapsed = false"
						>
							<ComposeMailEditor
								v-if="mail.draft && !isMobile"
								v-model="mail.show"
								:reload-mails="reload"
								:mail-details="draftMails[mail.name]"
								:is-in-thread="true"
								@discard-mail="discardLocalDraft(mail.name)"
								@reply="reply(getSourceMail(mail.name))"
								@reply-all="replyAll(getSourceMail(mail.name))"
								@forward="forward(getSourceMail(mail.name))"
								@pop-out="
									(mailDetails: ComposeMailData) => popOutDraft(mailDetails)
								"
							/>

							<template v-else-if="!mail.name.startsWith('draft')">
								<div
									v-if="isMobile && !isCollapsed(mail)"
									class="flex items-center justify-between pb-2"
									@click.stop="mail.collapsed = !mail.collapsed"
								>
									<div class="flex items-center space-x-2">
										<Badge
											v-if="mail.draft"
											:label="__('Draft')"
											theme="red"
											class="w-fit"
										/>
										<MailDate :datetime="mail.received_at" />
									</div>
									<MailActions
										:mailbox
										:mail
										:draft-mail="draftMails[mail.name]"
										:is-collapsed="isCollapsed(mail)"
										:show-reply-all="showReplyAll(mail)"
										:pop-out-draft
										:reply
										:reply-all
										:forward
										:reload-mails="handleReload"
										:thread="thread.data"
										@set-flagged="
											(id: string, flagged: boolean) =>
												emit('setFlagged', [id], flagged)
										"
									/>
								</div>
								<div
									class="flex items-center space-x-3"
									:class="{
										'cursor-pointer':
											mail !== thread.data[thread.data.length - 1],
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
										size="2xl"
									/>
									<div class="flex flex-1 justify-between truncate text-sm">
										<div class="mr-3 flex flex-col space-y-1 truncate">
											<div class="flex items-center space-x-1.5">
												<span
													class="truncate text-[15px] !font-semibold sm:text-base"
												>
													{{ mail.from_name || mail.from_email }}
												</span>
												<span
													v-if="mail.from_name && !isMobile"
													class="text-ink-gray-5 truncate"
												>
													{{ `<${mail.from_email}>` }}
												</span>
												<template
													v-if="!(isCollapsed(mail) || mail.draft)"
												>
													<ChevronDown
														v-if="isMobile"
														class="text-ink-gray-6 h-3.5 w-3.5 rounded-sm transition-transform duration-200"
														:class="{
															'rotate-180':
																showMailDetails === mail.name,
														}"
														@click.stop="
															showMailDetails =
																showMailDetails === mail.name
																	? undefined
																	: mail.name
														"
													/>
													<MailDetailsPopover v-else :mail />
												</template>
											</div>
											<div class="truncate">
												{{ getFormattedRecipients(mail.recipients) }}
											</div>
										</div>
										<div class="flex items-center space-x-1 self-start">
											<MailDate
												v-if="!isMobile || isCollapsed(mail)"
												:datetime="mail.received_at"
											/>
											<MailActions
												v-if="!isMobile"
												:mailbox
												:mail
												:is-collapsed="isCollapsed(mail)"
												:show-reply-all="showReplyAll(mail)"
												:pop-out-draft
												:reply
												:reply-all
												:forward
												:reload-mails="handleReload"
												:thread="thread.data"
												@set-flagged="
													(id: string, flagged: boolean) =>
														emit('setFlagged', [id], flagged)
												"
											/>
										</div>
									</div>
								</div>

								<MailDetails
									v-if="!isCollapsed(mail) && showMailDetails === mail.name"
									:mail
									class="mb-4"
								/>

								<div v-show="isCollapsed(mail)" class="truncate">
									{{ mail.preview }}
								</div>

								<div v-show="!isCollapsed(mail)">
									<Alert
										v-if="blockedAddresses.data.includes(mail.from_email)"
										:title="__('This sender is blocked')"
										:description="
											__(
												`{0} is currently on your block list. You won't receive new messages from this source until you unblock them.`,
												[mail.from_name || mail.from_email],
											)
										"
										class="mb-4"
										:dismissable="false"
									>
										<template #footer>
											<div class="col-span-full">
												<Button
													:label="__('Unblock')"
													variant="outline"
													@click="
														unblockEmailAddress.submit(mail.from_email)
													"
												/>
											</div>
										</template>
									</Alert>
									<EmailContent
										v-if="hasHtmlContent(mail.html_body)"
										:content="mail.html_body"
									/>
									<pre
										v-else
										class="whitespace-pre-wrap break-words pt-4 text-base !leading-5 sm:text-sm"
										>{{ mail.html_body || mail.text_body }}</pre
									>

									<div
										v-if="filteredAttachments(mail).length"
										class="mt-8 flex flex-wrap"
									>
										<AttachmentCapsule
											v-for="(attachment, idx) in filteredAttachments(mail)"
											:key="idx"
											:file-name="attachment.filename"
											:blob-i-d="attachment.blob_id"
											:type="attachment.type"
											class="mb-2 mr-2"
											@click.stop.prevent="
												openAttachment(
													filteredAttachments(mail),
													Number(idx),
												)
											"
										/>
									</div>
								</div>
							</template>
						</div>
					</template>
				</template>

				<div
					v-if="thread.data.length && !thread.data?.at(-1)?.draft"
					class="flex"
					:class="
						isMobile
							? 'bg-surface-white absolute bottom-0 left-0 right-0 z-20 items-stretch border-t'
							: 'items-center space-x-2'
					"
				>
					<Button
						v-for="action in replyForwardActions"
						:key="action.label"
						:icon-left="action.icon"
						:label="action.label"
						:tooltip="action.tooltip"
						:variant="isMobile ? 'ghost' : 'outline'"
						:class="{ '!h-16 flex-1 rounded-none': isMobile }"
						@click="action.onClick"
					/>
				</div>
			</div>
		</div>
		<SendMail
			v-if="focusedDraft"
			v-model="showSendModal"
			:mail-details="draftMails[focusedDraft]"
			@reload-mails="reload"
			@discard-mail="discardLocalDraft(focusedDraft)"
		/>
		<AttachmentViewer
			v-model="showAttachmentViewer"
			:attachments="attachments"
			:initial-index="attachmentIndex"
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
import { useRoute, useRouter } from 'vue-router'
import { ChevronDown, Forward, Reply, ReplyAll } from 'lucide-vue-next'
import { Alert, Avatar, Badge, Button, createResource } from 'frappe-ui'

import {
	extractQuotedContent,
	getFirstAlphabet,
	getFormattedDate,
	getFormattedRecipients,
	getGroupedRecipients,
	hasHtmlContent,
	raiseToast,
	shouldIgnoreKeypress,
} from '@/utils'
import { useScreenSize, useTheme } from '@/utils/composables'
import { userStore } from '@/stores/user'
import AttachmentCapsule from '@/components/AttachmentCapsule.vue'
import AttachmentViewer from '@/components/AttachmentViewer.vue'
import ComposeMailEditor from '@/components/ComposeMailEditor.vue'
import EmailContent from '@/components/EmailContent.vue'
import NoMails from '@/components/Icons/NoMails.vue'
import MailActions from '@/components/MailActions.vue'
import MailDate from '@/components/MailDate.vue'
import MailDetails from '@/components/MailDetails.vue'
import MailDetailsPopover from '@/components/MailDetailsPopover.vue'
import MailThreadPlaceholder from '@/components/MailThreadPlaceholder.vue'
import SendMail from '@/components/SendMail.vue'
import ThreadHeader from '@/components/ThreadHeader.vue'

import type { Attachment, ComposeMailData, Identity, Mail } from '@/types'

const { mailbox, threadID, threads } = defineProps<{
	mailbox: string
	threadID?: string
	threads: string[]
}>()

const emit = defineEmits([
	'reloadMails',
	'setSpamStatus',
	'archiveThread',
	'deleteThread',
	'setSeen',
	'setFlagged',
	'moveThread',
	'prevThread',
	'nextThread',
])

const { isMobile } = useScreenSize()
const dayjs = inject('$dayjs')
const user = inject('$user')
const store = userStore()
const { mailboxIds, identities, blockedAddresses } = store
const { dataTheme } = useTheme()

const route = useRoute()
const router = useRouter()

const threadContainerRef = useTemplateRef('threadContainer')
const unseenMarkerRef = useTemplateRef('unseenMarker')
const mailsRef = useTemplateRef('mails')
const scrollToLatestMail = () => {
	if (thread.data?.length > 1 && isSomeSeen.value)
		setTimeout(() => {
			const el =
				unseenMarkerRef.value?.[0] || unseenMarkerRef.value || mailsRef.value?.at(-1)
			if (!el || !threadContainerRef.value) return

			const offset = isMobile.value ? 52 : 64
			threadContainerRef.value.scrollTo({ top: el.offsetTop - offset, behavior: 'smooth' })
		}, 500)
}

const draftMails = reactive<{ [key: string]: ComposeMailData }>({})

const mailsByDay = computed(() => {
	const groups: { date: string; mails: Mail[] }[] = []
	for (const mail of thread.data || []) {
		const day = mail.received_at ? dayjs(mail.received_at).format('YYYY-MM-DD') : ''
		const last = groups.at(-1)
		if (last && last.date === day) last.mails.push(mail)
		else groups.push({ date: day, mails: [mail] })
	}
	return groups
})

const isSomeSeen = computed(() => (thread.data || []).some((m) => m.seen))
const unseenCount = computed(() => (thread.data || []).filter((m) => !m.seen && !m.draft).length)
const firstUnseenMail = computed(() => thread.data?.find((m) => !m.seen && !m.draft)?.id)

const shouldShowMarker = (id: string) =>
	isSomeSeen.value && firstUnseenMail.value && id == firstUnseenMail.value && !isMobile.value

const goToMailbox = () => router.push({ name: 'Mailbox', params: { mailbox }, query: route.query })

const thread = createResource({
	url: 'mail.api.mail.get_thread',
	auto: !!threadID,
	makeParams: () => ({ account: store.account, thread_id: threadID }),
	transform: (data: Mail[]) =>
		data
			.filter((mail) => filterRelevantMails(mail))
			.map((mail) => ({
				...mail,
				groupedRecipients: getGroupedRecipients(mail.recipients, false),
				collapsed: !!mail.seen,
				show: true,
			})),
	onSuccess: (data: Mail[]) => {
		if (!data.filter((mail) => filterRelevantMails(mail)).length) {
			goToMailbox()
			emit('reloadMails')
			return
		}

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
		scrollToLatestMail()
	},
	onError: () => goToMailbox(),
})

const filterRelevantMails = (mail: Mail) => {
	if (mailbox === 'search') return true

	const mailboxes = mail.mailboxes.map((m) => m.mailbox_id)
	const trash = mailboxIds.trash
	if (mailbox === trash) return mailboxes.includes(trash)

	if (mailbox === mailboxIds.junk) return !!mail.junk

	return !mailboxes.includes(trash) && !mail.junk
}

const reload = () => {
	if (threadID) thread.reload()
}

watch(() => threadID, reload)

const unblockEmailAddress = createResource({
	url: 'mail.api.mail.unblock_email_addresses',
	makeParams: (email) => ({ account: store.account, emails: [email] }),
	onSuccess: () => {
		raiseToast(__('Email address unblocked.'))
		blockedAddresses.reload()
	},
})

const handleReload = (isUndo = false) => {
	if (thread.data.length == 1) {
		emit('reloadMails')
		if (!isUndo) return goToMailbox()
	}
	reload()
}

const replyForwardActions = computed(() =>
	[
		{
			label: __('Reply'),
			tooltip: __('Reply (R)'),
			onClick: () => reply(thread.data.at(-1)),
			icon: Reply,
		},
		{
			label: __('Reply All'),
			tooltip: __('Reply All (Shift+R)'),
			onClick: () => replyAll(thread.data.at(-1)),
			icon: ReplyAll,
			condition: showReplyAll(thread.data.at(-1)),
		},
		{
			label: __('Forward'),
			tooltip: __('Forward (F)'),
			onClick: () => forward(thread.data.at(-1)),
			icon: Forward,
		},
	].filter((action) => action.condition !== false),
)

const showMailDetails = ref<string>()

const filteredAttachments = (mail: Mail) =>
	mail.attachments.filter(
		(a: Attachment) => a.disposition === 'attachment' || !a.type.startsWith('image/'),
	)

const showAttachmentViewer = ref(false)
const attachments = ref<Attachment[]>([])
const attachmentIndex = ref(0)

const openAttachment = (mailAttachments: Attachment[], idx: number) => {
	attachments.value = mailAttachments
	attachmentIndex.value = idx
	showAttachmentViewer.value = true
}

const isCollapsed = (mail: Mail) =>
	!!(mail.collapsed && mail !== thread.data[thread.data.length - 1])

const showReplyAll = (mail: Mail) =>
	!mail.draft &&
	mail.groupedRecipients.to
		?.concat(mail.groupedRecipients.cc)
		.filter((m) => m !== user.data.email).length > 0

const populateDraftMails = (mail: Mail) =>
	(draftMails[mail.name] = {
		name: mail.name,
		id: mail.id,
		from_email: mail.from_email,
		to: mail.groupedRecipients.to,
		cc: mail.groupedRecipients.cc,
		bcc: mail.groupedRecipients.bcc,
		subject: mail.subject || '',
		in_reply_to: mail.message_id,
		in_reply_to_id: mail.id,
		attachments: mail.attachments || [],
		...extractQuotedContent(mail.html_body),
	})

const reply = (mail: Mail) =>
	createLocalDraft(mail, {
		...getReplyDetails(mail),
		...getReplyRecipients(mail),
		type: 'reply',
	})

const replyAll = (mail: Mail) =>
	createLocalDraft(mail, {
		...getReplyDetails(mail),
		...getReplyAllRecipients(mail),
		type: 'replyAll',
	})

const forward = (mail: Mail) =>
	createLocalDraft(mail, {
		subject: `Fwd: ${mail.subject || ''}`,
		html_body: getForwardedContent(mail),
		attachments: mail.attachments || [],
		forwarded_from_id: mail.id,
		type: 'forward',
	})

const createLocalDraft = (mail: Mail, draftDetails: ComposeMailData) => {
	mail.collapsed = false
	const name = `draft:${mail.name}`
	if (name in draftMails) discardLocalDraft(name)

	nextTick(() => {
		draftMails[name] = { name, ...draftDetails }
		const index = thread.data.indexOf(mail)
		const draft = thread.data.find((m: Mail) => m.name === name)
		if (index !== -1 && !draft)
			thread.data.splice(index + 1, 0, { ...draftMails[name], draft: 1, show: true })
		if (isMobile.value) popOutDraft(draftMails[name])
		else
			setTimeout(() =>
				threadContainerRef.value
					?.querySelector(`[data-mail-name="${name}"]`)
					?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
			)
	})
}

const discardLocalDraft = (mail: string) => {
	delete draftMails[mail]
	thread.data = thread.data.filter((m: Mail) => m.name !== mail)
}

// Shortcuts

const handleKeydown = (e: KeyboardEvent) => {
	if (shouldIgnoreKeypress(e)) return

	const key = e.key.toLowerCase()
	const lastMail = thread.data?.at(-1)
	if (!lastMail || lastMail.draft) return

	// Reply/Reply All shortcut
	if (key === 'r') {
		e.preventDefault()
		if (e.shiftKey) replyAll(lastMail)
		else reply(lastMail)
		return
	}

	// Forward shortcut
	if (key === 'f') {
		e.preventDefault()
		forward(lastMail)
	}
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown))

const syncFlagged = (ids: string[], flagged: boolean) =>
	thread.data?.forEach((mail: Mail) => {
		if (ids.includes(mail.id)) mail.flagged = flagged ? 1 : 0
	})

defineExpose({ syncFlagged })

const focusedDraft = ref<string>()
const showSendModal = ref(false)

const popOutDraft = (mail: ComposeMailData) => {
	draftMails[mail.name as string] = mail
	focusedDraft.value = mail.name
	showSendModal.value = true
}

const getSourceMail = (mail: string) =>
	thread.data.find((m: Mail) => m.name === mail.split(':')[1])

const getReplyDetails = (mail: Mail) => ({
	subject: mail.subject?.startsWith('Re: ') ? mail.subject : `Re: ${mail.subject}`,
	quoted_content: getQuotedContent(mail),
	attachments: mail.attachments?.filter((a: Attachment) => a.disposition === 'inline') || [],
	in_reply_to: mail.message_id,
	in_reply_to_id: mail.id,
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

const isUserEmail = (email: string) =>
	identities.data.map((i: Identity) => i.email).includes(email)

const getBodyContent = (mail: Mail) => {
	if (hasHtmlContent(mail.html_body)) return mail.html_body
	return `<pre style="white-space: pre-wrap; word-break: break-word">${mail.html_body || mail.text_body || '&nbsp;'}</pre>`
}

const getQuotedContent = (mail: Mail) =>
	`
		<div class="frappe_mail_quote">
			On ${dayjs(mail.received_at).format('DD MMM YYYY [at] h:mm A')}, ${mail.from_email} wrote:
			<blockquote style="margin-left: 8px">
				${getBodyContent(mail)}
			</blockquote>
		</div>
	`

const getForwardedContent = (mail: Mail) =>
	`
		<div class="frappe_mail_fwd">
			<br><br>
			---------- Forwarded message ---------<br>
			From: ${mail.from_name} < ${mail.from_email} ><br>
			Date: ${dayjs(mail.received_at).format('ddd, MMM D, YYYY [at] h:mm A')}<br>
			Subject: ${mail.subject || ''}<br>
			To: ${mail.groupedRecipients.to.join(', ')}<br>
			${mail.groupedRecipients.cc.length ? `Cc: ${mail.groupedRecipients.cc.join(', ')}<br>` : ''}
			<br><br>
			${getBodyContent(mail)}
		</div>
	`
</script>
