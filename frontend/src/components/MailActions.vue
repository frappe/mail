<template>
	<Button
		v-for="action in primaryActions(mail).filter((d) => d.condition !== false && !isCollapsed)"
		:key="action.label"
		variant="ghost"
		:tooltip="action.label"
		@click.stop="action.onClick"
	>
		<template #icon>
			<component :is="action.icon" class="text-ink-gray-5 h-4 w-4" />
		</template>
	</Button>

	<Dropdown v-if="!mail.draft && !isCollapsed" :options="moreActions(mail)">
		<Button variant="ghost" :tooltip="__('More')" @click.stop>
			<template #icon>
				<Ellipsis class="text-ink-gray-5 h-4 w-4" />
			</template>
		</Button>
	</Dropdown>
</template>

<script lang="ts" setup>
import { h, inject } from 'vue'
import {
	Ban,
	CircleAlert,
	CircleCheck,
	Code,
	Ellipsis,
	ExternalLink,
	Forward,
	LockOpen,
	MailOpen,
	Reply,
	ReplyAll,
	SquarePen,
	Star,
	Trash2,
} from 'lucide-vue-next'
import { Button, Dropdown, createResource, toast } from 'frappe-ui'

import { raisePromiseToast, raiseToast } from '@/utils'
import { useScreenSize, useUndo } from '@/utils/composables'
import { userStore } from '@/stores/user'

import type { ComposeMailData, Identity, Mail } from '@/types'

const {
	mailbox,
	mail,
	draftMail,
	isCollapsed,
	showReplyAll,
	popOutDraft,
	reply,
	replyAll,
	forward,
	reloadMails,
	thread,
} = defineProps<{
	mailbox: string
	mail: Mail
	draftMail?: ComposeMailData
	isCollapsed: boolean
	showReplyAll: boolean
	popOutDraft: (mail: ComposeMailData) => void
	reply: (mail: Mail) => void
	replyAll: (mail: Mail) => void
	forward: (mail: Mail) => void
	reloadMails: (isUndo?: boolean) => void
	thread: Mail[]
}>()

const { isMobile } = useScreenSize()
const { account, mailboxes, mailboxIds, identities, blockedAddresses } = userStore()
const { setUndoAction, undo } = useUndo()
const user = inject('$user')

const primaryActions = (mail: Mail): MailAction[] => [
	{
		label: __('Unstar'),
		onClick: () => starMails.submit({ ids: [mail.id], flagged: false }),
		icon: () => h(Star, { class: 'fill-ink-amber-2 text-ink-amber-2 stroke-ink-amber-2' }),
		condition: !!mail.flagged && mailbox !== mailboxIds.trash && !isMobile.value,
	},
	{
		label: __('Star'),
		onClick: () => starMails.submit({ ids: [mail.id], flagged: true }),
		icon: Star,
		condition: !mail.flagged && !mail.draft && mailbox !== mailboxIds.trash && !isMobile.value,
	},
	{
		label: __('Edit Draft'),
		onClick: () => popOutDraft(draftMail!),
		icon: SquarePen,
		condition: !!mail.draft && isMobile.value,
	},
	{
		label: __('Reply'),
		onClick: () => (showReplyAll ? replyAll(mail) : reply(mail)),
		icon: Reply,
		condition: !mail.draft && !isMobile.value,
	},
]

interface MailAction {
	label: string
	onClick: () => void
	icon: typeof SquarePen
	condition?: boolean | (() => boolean)
}

interface GroupedAction {
	group: string
	items: MailAction[]
}

const moreActions = (mail: Mail): GroupedAction[] => [
	{
		group: '',
		items: [
			{
				label: __('Reply'),
				onClick: () => setTimeout(() => reply(mail), 300),
				icon: Reply,
				condition: () => !mail.draft,
			},
			{
				label: __('Reply All'),
				onClick: () => setTimeout(() => replyAll(mail), 300),
				icon: ReplyAll,
				condition: () => showReplyAll,
			},
			{
				label: __('Forward'),
				onClick: () => setTimeout(() => forward(mail), 300),
				icon: Forward,
				condition: () => !mail.draft,
			},
		],
	},
	{
		group: '',
		items: [
			{
				label: __('Unstar'),
				onClick: () => starMails.submit({ ids: [mail.id], flagged: false }),
				icon: () =>
					h(Star, { class: 'fill-ink-amber-2 text-ink-amber-2 stroke-ink-amber-2' }),
				condition: () => !!mail.flagged && mailbox !== mailboxIds.trash,
			},
			{
				label: __('Star'),
				onClick: () => starMails.submit({ ids: [mail.id], flagged: true }),
				icon: Star,
				condition: () => !mail.flagged && !mail.draft && mailbox !== mailboxIds.trash,
			},
			{
				label: __('Mark as Junk'),
				onClick: () => handleMarkAsSpam(true),
				icon: CircleAlert,
				condition: () => mailbox !== mailboxIds.drafts && mail.junk === 0,
			},
			{
				label: __('Mark as Not Junk'),
				onClick: () => handleMarkAsSpam(false),
				icon: CircleCheck,
				condition: () => mail.junk === 1,
			},
			{
				label: __('Move to Trash'),
				onClick: () => handleMoveMail(mailboxIds.trash),
				icon: Trash2,
				condition: () => mailbox !== mailboxIds.trash,
			},
			{
				label: __('Delete Message'),
				onClick: () => handleDeleteMail(),
				icon: Trash2,
				condition: () => mailbox === mailboxIds.trash,
			},
			{
				label: thread.length === 1 ? __('Mark as Unread') : __('Mark Unread from Here'),
				onClick: () => handleMarkUnreadFromHere(),
				icon: MailOpen,
				condition: () => !mail.draft && mail.seen,
			},
			{
				label: __('Block Sender'),
				onClick: () => handleBlockAddress(true),
				icon: Ban,
				condition: () =>
					!identities.data.some((i: Identity) => i.email === mail.from_email) &&
					!blockedAddresses.data?.includes(mail.from_email),
			},
			{
				label: __('Unblock Sender'),
				onClick: () => handleBlockAddress(false),
				icon: LockOpen,
				condition: () => blockedAddresses.data?.includes(mail.from_email),
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

const markAsSpam = createResource({
	url: 'mail.api.mail.set_mails_spam_status',
	makeParams: ({ spam }: { spam: boolean }) => ({ account, ids: [mail.id], spam }),
})

const handleMarkAsSpam = (spam: boolean, isUndo = false) => {
	const action = () => markAsSpam.submit({ spam }).then(() => reloadMails(isUndo))
	const successMessage = spam ? __('Mail marked as Junk.') : __('Mail marked as Not Junk.')

	if (isUndo) return raisePromiseToast(action, __('Undoing...'), successMessage)

	setUndoAction(() => handleMarkAsSpam(!spam, true))
	raisePromiseToast(
		action,
		spam ? __('Marking as Junk...') : __('Marking as Not Junk...'),
		successMessage,
		undo,
	)
}

const moveMail = createResource({
	url: 'mail.api.mail.move_mails',
	makeParams: (mailbox: string) => ({ account, ids: [mail.id], mailbox }),
})

const handleMoveMail = (mailbox: string, isUndo = false) => {
	const action = () => moveMail.submit(mailbox).then(() => reloadMails(isUndo))
	const mailboxName = mailboxes.data?.find((m) => m.id === mailbox)._name

	if (isUndo)
		return raisePromiseToast(
			action,
			__('Undoing...'),
			__('Mail moved back to {0}.', [mailboxName]),
		)

	setUndoAction(() => handleMoveMail(mail.mailboxes[0].mailbox_id, true))
	raisePromiseToast(
		action,
		__('Moving to {0}...', [mailboxName]),
		__('Mail moved to {0}.', [mailboxName]),
		undo,
	)
}

const deleteMail = createResource({
	url: 'mail.client.doctype.mail_message.mail_message.bulk_delete',
	makeParams: () => ({ names: [mail.name] }),
	onSuccess: () => reloadMails(),
})

const handleDeleteMail = () =>
	toast.promise(deleteMail.submit(), {
		loading: __('Deleting...'),
		success: __('Mail deleted.'),
		error: __('Action failed. Please try again in some time.'),
	})

const starMails = createResource({
	url: 'mail.api.mail.set_flagged',
	makeParams: ({ ids, flagged }: { ids: string[]; flagged: boolean }) => ({
		account,
		ids,
		flagged,
	}),
	onSuccess: ({ ids, flagged }: { ids: string[]; flagged: boolean }) => {
		ids.forEach((id: string) => {
			const m = thread.find((m: Mail) => m.id === id)
			if (m) m.flagged = flagged ? 1 : 0
		})
	},
})

const setMailsSeen = createResource({
	url: 'mail.api.mail.set_mails_seen',
	makeParams: ({ ids }: { ids: string[] }) => ({ account, ids, seen: false }),
	onSuccess: (ids: string[]) => {
		raiseToast(__('{0} marked as unread.', [ids.length === 1 ? __('Mail') : __('Mails')]))
		ids.forEach((id: string) => {
			const m = thread.find((m: Mail) => m.id === id)
			if (m) m.seen = 0
		})
	},
})

const handleMarkUnreadFromHere = () => {
	const idx = thread.indexOf(mail)
	if (idx === -1) return
	const ids = thread
		.slice(idx)
		.filter((m: Mail) => !m.draft && m.seen)
		.map((m: Mail) => m.id)
	if (ids.length) setMailsSeen.submit({ ids })
}

const blockEmailAddress = createResource({
	url: 'mail.api.mail.block_email_address',
	makeParams: () => ({ account, email: mail.from_email }),
})

const unblockEmailAddress = createResource({
	url: 'mail.api.mail.unblock_email_addresses',
	makeParams: () => ({ account, emails: [mail.from_email] }),
})

const handleBlockAddress = (block: boolean, isUndo = false) => {
	const action = () =>
		(block ? blockEmailAddress : unblockEmailAddress)
			.submit()
			.then(() => blockedAddresses.reload())
	const successMessage = block ? __('Email address blocked.') : __('Email address unblocked.')

	if (isUndo) return raisePromiseToast(action, __('Undoing...'), successMessage)

	setUndoAction(() => handleBlockAddress(!block, true))
	raisePromiseToast(
		action,
		block ? __('Blocking email address...') : __('Unblocking email address...'),
		successMessage,
		undo,
	)
}
</script>
