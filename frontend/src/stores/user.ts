import { computed } from 'vue'
import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'

import router from '@/router'
import { getDataTheme } from '@/utils'

import type { UserResource } from '@/types'

export type MailboxRole = 'inbox' | 'sent' | 'drafts' | 'trash' | 'junk' | 'archive' | 'important'

export const userStore = defineStore('mail-users', () => {
	const userResource: UserResource = createResource({
		url: 'mail.api.account.get_user_info',
		onSuccess: (data) => {
			document.documentElement.setAttribute('data-theme', getDataTheme(data.color_scheme))

			if (data?.is_mail_admin) {
				domains.fetch()
				tenantOwner.fetch(data.tenant)
			}

			if (!data?.is_mail_user) return

			mailboxes.fetch()
			addressBooks.fetch()
			identities.fetch()
			sieveScripts.fetch()
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

	const tenantOwner = createResource({
		url: 'frappe.client.get_value',
		makeParams: (tenant: string) => ({
			doctype: 'Mail Tenant',
			fieldname: 'user',
			filters: tenant,
			as_dict: false,
		}),
	})

	const domains = createResource({ url: 'mail.api.admin.get_verified_domains' })

	const sieveScripts = createResource({ url: 'mail.api.account.get_sieve_scripts' })

	return {
		userResource,
		mailboxes,
		mailboxIds,
		addressBooks,
		identities,
		tenantOwner,
		domains,
		sieveScripts,
	}
})
