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
		<span @click.stop>
			<Button variant="ghost" :tooltip="__('More')">
				<template #icon>
					<Ellipsis class="text-ink-gray-5 h-4 w-4" />
				</template>
			</Button>
		</span>
	</Dropdown>
</template>

<script lang="ts" setup>
import { h, inject } from 'vue'
import {
	BadgeAlert,
	Code,
	Ellipsis,
	ExternalLink,
	Forward,
	Reply,
	ReplyAll,
	SquarePen,
	Star,
	Trash2,
} from 'lucide-vue-next'
import { Button, Dropdown, createResource, toast } from 'frappe-ui'

import { useScreenSize } from '@/utils/composables'
import { userStore } from '@/stores/user'

import type { ComposeMailData, Mail } from '@/types'

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
}>()

const emit = defineEmits(['reloadMails', 'starMails'])

const { isMobile } = useScreenSize()
const { mailboxes, mailboxIds } = userStore()
const user = inject('$user')

const primaryActions = (mail: Mail): MailAction[] => [
	{
		label: __('Unstar'),
		onClick: () => starMails.submit({ _ids: [mail._id], flagged: false }),
		icon: () => h(Star, { class: 'fill-ink-amber-2 text-ink-amber-2 stroke-ink-amber-2' }),
		condition: !!mail.flagged && mailbox !== mailboxIds.trash && !isMobile.value,
	},
	{
		label: __('Star'),
		onClick: () => starMails.submit({ _ids: [mail._id], flagged: true }),
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
		onClick: () => reply(mail),
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
				onClick: () => reply(mail),
				icon: Reply,
				condition: () => !mail.draft,
			},
			{
				label: __('Reply All'),
				onClick: () => replyAll(mail),
				icon: ReplyAll,
				condition: () => showReplyAll,
			},
			{
				label: __('Forward'),
				onClick: () => forward(mail),
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
				onClick: () => starMails.submit({ _ids: [mail._id], flagged: false }),
				icon: () =>
					h(Star, { class: 'fill-ink-amber-2 text-ink-amber-2 stroke-ink-amber-2' }),
				condition: () => !!mail.flagged && mailbox !== mailboxIds.trash,
			},
			{
				label: __('Star'),
				onClick: () => starMails.submit({ _ids: [mail._id], flagged: true }),
				icon: Star,
				condition: () => !mail.flagged && !mail.draft && mailbox !== mailboxIds.trash,
			},
			{
				label: __('Mark as Junk'),
				onClick: () => handleMarkAsSpam(),
				icon: BadgeAlert,
				condition: () => ![mailboxIds.junk, mailboxIds.drafts].includes(mailbox),
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
	makeParams: () => ({ _ids: [mail._id], spam: true }),
	onSuccess: () => emit('reloadMails'),
})

const handleMarkAsSpam = () =>
	toast.promise(markAsSpam.submit(), {
		loading: __('Marking as Junk...'),
		success: __('Mail marked as Junk.'),
		error: __('Action failed. Please try again in some time.'),
	})

const moveMail = createResource({
	url: 'mail.api.mail.move_mails',
	makeParams: (mailbox: string) => ({ _ids: [mail._id], mailbox }),
	onSuccess: () => emit('reloadMails'),
})

const handleMoveMail = (mailbox: string) => {
	const mailboxName = mailboxes.data?.find((m) => m.id === mailbox)._name

	toast.promise(moveMail.submit(mailbox), {
		loading: __('Moving to {0}...', [mailboxName]),
		success: __('Mail moved to {0}.', [mailboxName]),
		error: __('Action failed. Please try again in some time.'),
	})
}

const deleteMail = createResource({
	url: 'mail.mail.doctype.mail_message.mail_message.bulk_delete',
	makeParams: () => ({ names: [mail.name] }),
	onSuccess: () => emit('reloadMails'),
})

const handleDeleteMail = () =>
	toast.promise(deleteMail.submit(), {
		loading: __('Deleting...'),
		success: __('Mail deleted.'),
		error: __('Action failed. Please try again in some time.'),
	})

const starMails = createResource({
	url: 'mail.api.mail.set_flagged',
	makeParams: ({ _ids, flagged }: { _ids: string[]; flagged: boolean }) => ({
		_ids,
		flagged,
	}),
	onSuccess: ({ _ids, flagged }: { _ids: string[]; flagged: boolean }) =>
		emit('starMails', _ids, Number(flagged)),
})
</script>
