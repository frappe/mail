import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'

import router from '@/router'

import type { UserResource } from '@/types'

export type MailboxRole = 'inbox' | 'sent' | 'drafts' | 'trash' | 'junk' | 'archive' | 'important'

const ACCOUNT_STORAGE_KEY = 'mail-account-id'

export const userStore = defineStore('mail-user', () => {
	const accountId = ref(localStorage.getItem(ACCOUNT_STORAGE_KEY) || '')

	const setAccount = (id: string) => {
		accountId.value = id
		localStorage.setItem(ACCOUNT_STORAGE_KEY, id)
		mailboxes.fetch()
		addressBooks.fetch()
		identities.fetch()
		blockedAddresses.fetch()
		sieveScripts.fetch()
	}

	const userResource: UserResource = createResource({
		url: 'mail.api.account.get_user_info',
		onSuccess: (data) => {
			if (data?.is_mail_admin) domains.fetch()
		},
		onError: (error) => {
			if (error && error.exc_type === 'AuthenticationError') router.push('/login')
		},
		auto: true,
	})

	const account = computed(
		() => userResource.data?.accounts?.find((a) => a.id === accountId.value)?.name,
	)

	const mailboxes = createResource({
		url: 'mail.api.mail.get_mailboxes',
		makeParams: () => ({ account: account.value }),
		cache: ['mailboxes', accountId.value],
	})

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

	const addressBooks = createResource({
		url: 'mail.api.contacts.get_address_books',
		makeParams: () => ({ account: account.value }),
		cache: ['addressBooks', accountId.value],
	})

	const identities = createResource({
		url: 'mail.api.account.get_identities',
		makeParams: () => ({ account: account.value }),
		cache: ['identities', accountId.value],
	})

	const blockedAddresses = createResource({
		url: 'mail.api.mail.get_blocked_addresses',
		makeParams: () => ({ account: account.value }),
		cache: ['blockedAddresses', accountId.value],
	})

	const sieveScripts = createResource({
		url: 'mail.api.sieve.get_sieve_scripts',
		makeParams: () => ({ account: account.value }),
		cache: ['sieveScripts', accountId.value],
	})

	const domains = createResource({ url: 'mail.api.admin.get_verified_domains' })

	return {
		accountId,
		account,
		setAccount,
		userResource,
		mailboxes,
		mailboxIds,
		addressBooks,
		identities,
		domains,
		sieveScripts,
		blockedAddresses,
	}
})
