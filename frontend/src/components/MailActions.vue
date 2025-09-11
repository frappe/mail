<template>
	<Tooltip
		v-for="action in primaryActions(mail).filter((d) => d.condition !== false && !isCollapsed)"
		:key="action.label"
		:text="action.label"
	>
		<Button variant="ghost" @click.stop="action.onClick">
			<template #icon>
				<component :is="action.icon" class="text-ink-gray-5 h-4 w-4" />
			</template>
		</Button>
	</Tooltip>

	<Tooltip v-if="!mail.draft && !isCollapsed" :text="__('More')">
		<Dropdown :options="moreActions(mail)">
			<span @click.stop>
				<Button variant="ghost">
					<template #icon>
						<Ellipsis class="text-ink-gray-5 h-4 w-4" />
					</template>
				</Button>
			</span>
		</Dropdown>
	</Tooltip>
</template>

<script lang="ts" setup>
import { h, inject } from 'vue'
import {
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
import { Button, Dropdown, Tooltip, createResource } from 'frappe-ui'

import { useScreenSize } from '@/utils/composables'
import { userStore } from '@/stores/user'

import type { Mail } from '@/types'

const { mailbox, mail, isCollapsed, showReplyAll, popOutDraft, reply, replyAll, forward } =
	defineProps<{
		mailbox: string
		mail: Mail
		isCollapsed: boolean
		showReplyAll: boolean
		popOutDraft: (mail: Mail) => void
		reply: (mail: Mail) => void
		replyAll: (mail: Mail) => void
		forward: (mail: Mail) => void
	}>()

const emit = defineEmits(['reloadMails', 'deleteMails', 'starMails'])

const { isMobile } = useScreenSize()
const { mailboxIds } = userStore()
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
		onClick: () => popOutDraft(mail),
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

const moveMail = createResource({
	url: 'mail.api.mail.move_mails',
	makeParams: ({ _ids, mailbox }: { _ids: string[]; mailbox: string }) => ({ _ids, mailbox }),
	onSuccess: () => emit('reloadMails'),
})

const deleteMails = createResource({
	url: 'mail.mail.doctype.mail_message.mail_message.bulk_delete',
	makeParams: (names: string[]) => ({ names }),
	onSuccess: () => emit('deleteMails'),
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
