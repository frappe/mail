import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'

import { SCREENING_MAILBOX_NAME } from '@/constants'

import type { UserAccount, UserResource } from '@/types'

export type MailboxRole = 'inbox' | 'sent' | 'drafts' | 'trash' | 'junk' | 'archive' | 'important'

const ACCOUNT_STORAGE_KEY = 'mail-account-id'

export const userStore = defineStore('mail-user', () => {
	const accountId = ref('')

	const resolveAccount = (accounts?: UserAccount[], routeAccountId?: string) => {
		if (!accounts?.length) return

		// 1. Route param
		if (routeAccountId && accounts.some((a) => a.id === routeAccountId)) {
			if (routeAccountId !== accountId.value) setAccount(routeAccountId)
			return
		}

		// 2. localStorage
		const localId = localStorage.getItem(ACCOUNT_STORAGE_KEY)
		if (localId && accounts.some((a) => a.id === localId)) {
			if (localId !== accountId.value) setAccount(localId)
			return
		}

		// 3. Personal account fallback
		if (accountId.value) return
		const personalId = accounts.find((a) => a.is_personal)?.id
		if (personalId) setAccount(personalId)
	}

	const setAccount = (id: string) => {
		accountId.value = id
		localStorage.setItem(ACCOUNT_STORAGE_KEY, id)
		mailboxes.fetch()
		addressBooks.fetch()
		identities.fetch()
		screenedAddresses.fetch()
		sieveScripts.fetch()
	}

	const userResource: UserResource = createResource({
		url: 'mail.api.account.get_user_info',
		onSuccess: (data) => {
			if (data?.is_mail_admin) domains.fetch()
			resolveAccount(data?.accounts)
		},
		// Auth errors are handled centrally by the resource fetcher (see main.ts).
		auto: true,
	})

	// The logged-in user (the user component of every account handle is always the session user).
	// Exposed so callers can rebuild a `user:account_id` virtual-doctype document name when needed.
	const user = computed(() => userResource.data?.name)

	const mailboxes = createResource({
		url: 'mail.api.mail.get_mailboxes',
		makeParams: () => ({ account_id: accountId.value }),
		cache: ['mailboxes', accountId.value],
	})

	const mailboxIds = computed(() => {
		const ids: Record<MailboxRole | 'screening', string> = {
			inbox: '',
			sent: '',
			drafts: '',
			trash: '',
			junk: '',
			archive: '',
			important: '',
			screening: '',
		}
		mailboxes.data?.forEach((m: { role?: MailboxRole; _name?: string; id: string }) => {
			if (m.role) ids[m.role] = m.id
			else if (m._name === SCREENING_MAILBOX_NAME) ids.screening = m.id
		})
		return ids
	})

	const addressBooks = createResource({
		url: 'mail.api.contacts.get_address_books',
		makeParams: () => ({ account_id: accountId.value }),
		cache: ['addressBooks', accountId.value],
	})

	const identities = createResource({
		url: 'mail.api.account.get_identities',
		makeParams: () => ({ account_id: accountId.value }),
		cache: ['identities', accountId.value],
	})

	// Screened senders for the account: each is `{ email, action }` where action is 'Reject'
	// (discard incoming mail), 'Spam' (file it into the Spam folder), or 'Accepted'.
	const screenedAddresses = createResource({
		url: 'mail.api.mail.get_screened_addresses',
		makeParams: () => ({ account_id: accountId.value }),
		cache: ['screenedAddresses', accountId.value],
	})

	const sieveScripts = createResource({
		url: 'mail.api.sieve.get_sieve_scripts',
		makeParams: () => ({ account_id: accountId.value }),
		cache: ['sieveScripts', accountId.value],
	})

	const domains = createResource({ url: 'mail.api.admin.get_enabled_domains' })

	// Clear all user/account state so the next sign-in starts from a clean slate. Without
	// resetting accountId, resolveAccount() would see the resolved account as unchanged and skip
	// setAccount(), so the per-account resources (mailboxes, etc.) would never re-fetch until a
	// full page reload.
	const reset = () => {
		accountId.value = ''
		userResource.reset()
		mailboxes.reset()
		addressBooks.reset()
		identities.reset()
		screenedAddresses.reset()
		sieveScripts.reset()
		domains.reset()
	}

	return {
		accountId,
		user,
		resolveAccount,
		userResource,
		mailboxes,
		mailboxIds,
		addressBooks,
		identities,
		domains,
		sieveScripts,
		screenedAddresses,
		reset,
	}
})
