import { computed } from 'vue'
import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'

import router from '@/router'
import { type GroupMessagesBy, useLayout } from '@/utils/composables'

const { setShowReadingPane, setGroupMessagesBy } = useLayout()

import type { UserResource } from '@/types'

export type MailboxRole = 'inbox' | 'sent' | 'drafts' | 'trash' | 'junk' | 'archive' | 'important'

export const userStore = defineStore('mail-users', () => {
	const userResource: UserResource = createResource({
		url: 'mail.api.account.get_user_info',
		onSuccess: (data) => {
			if (!data?.is_mail_user) return

			mailboxes.fetch()
			identities.fetch()
			setShowReadingPane(
				data.name,
				localStorage.getItem(`user:${data.name}:showReadingPane`) === 'true',
			)
			setGroupMessagesBy(
				data.name,
				(localStorage.getItem(`user:${data.name}:groupMessagesBy`) as GroupMessagesBy) ||
					'day',
			)
		},
		onError: (error) => {
			if (error && error.exc_type === 'AuthenticationError') router.push('/login')
		},
		auto: true,
	})

	const mailboxes = createResource({ url: 'mail.api.mail.get_mailboxes' })

	const mailboxIds = computed(() => {
		const ids: Record<MailboxRole, string> = {
			inbox: '',
			sent: '',
			drafts: '',
			trash: '',
			junk: '',
			archive: '',
			important: '',
		}
		mailboxes.data?.forEach((m: { role?: MailboxRole; id: string }) => {
			if (m.role) ids[m.role] = m.id
		})
		return ids
	})

	const identities = createResource({ url: 'mail.api.account.get_identities' })

	return { userResource, mailboxes, mailboxIds, identities }
})
