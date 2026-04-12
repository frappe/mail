import { computed } from 'vue'
import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'

import router from '@/router'
import { type GroupMessagesBy, type Theme, useLayout, useTheme } from '@/utils/composables'

const { setShowReadingPane, setGroupMessagesBy } = useLayout()
const { setTheme } = useTheme()

const getThemeFromColorScheme = (
	colorScheme: 'System Default' | 'Light Mode' | 'Dark Mode' | undefined,
): Theme => {
	if (colorScheme === 'Light Mode') return 'light'
	if (colorScheme === 'Dark Mode') return 'dark'
	return 'system'
}

const getGroupMessagesByFromUserSettings = (
	groupMessagesBy: '' | 'Day' | 'Month' | undefined,
): GroupMessagesBy => {
	if (groupMessagesBy === 'Day') return 'day'
	if (groupMessagesBy === 'Month') return 'month'
	return 'none'
}

import type { UserResource } from '@/types'

export type MailboxRole = 'inbox' | 'sent' | 'drafts' | 'trash' | 'junk' | 'archive' | 'important'

export const userStore = defineStore('mail-users', () => {
	const userResource: UserResource = createResource({
		url: 'mail.api.account.get_user_info',
		onSuccess: (data) => {
			setTheme(getThemeFromColorScheme(data?.color_scheme))
			setShowReadingPane(!!data?.show_reading_pane)
			setGroupMessagesBy(getGroupMessagesByFromUserSettings(data?.group_messages_by))

			if (data?.is_mail_admin) {
				domains.fetch()
			}

			if (!data?.is_jmap_configured) return

			mailboxes.fetch()
			addressBooks.fetch()
			identities.fetch()
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

	const addressBooks = createResource({ url: 'mail.api.contacts.get_address_books' })

	const identities = createResource({ url: 'mail.api.account.get_identities' })

	const domains = createResource({ url: 'mail.api.admin.get_verified_domains' })

	return { userResource, mailboxes, mailboxIds, addressBooks, identities, domains }
})
