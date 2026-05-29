import { computed, ref } from 'vue'
import { ApplicationSettings } from '@nativescript/core'
import { defineStore } from 'pinia'

import { useApi } from '@/utils/api'

import type { MailboxData, User, UserAccount } from '@mail/types'

// Mirrors the shape of frontend/src/stores/user.ts — kept in sync intentionally.
export type MailboxRole = 'inbox' | 'sent' | 'drafts' | 'trash' | 'junk' | 'archive' | 'important'

const ACCOUNT_STORAGE_KEY = 'mail-account-id'

export const userStore = defineStore('mail-user', () => {
	const api = useApi()

	const user = ref<User | null>(null)
	const accountId = ref<string>(ApplicationSettings.getString(ACCOUNT_STORAGE_KEY, ''))
	const mailboxes = ref<MailboxData[]>([])
	const isLoading = ref(false)
	const error = ref<string | null>(null)

	const account = computed(
		() => user.value?.accounts?.find((a) => a.id === accountId.value)?.name ?? '',
	)

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
		mailboxes.value.forEach((m) => {
			if (m.role) ids[m.role as MailboxRole] = m.id
		})
		return ids
	})

	async function fetchUser() {
		isLoading.value = true
		error.value = null
		try {
			const data = await api.call<User>('mail.api.account.get_user_info')
			user.value = data
			resolveAccount(data.accounts)
		} catch (e) {
			error.value = e instanceof Error ? e.message : 'Failed to load user'
		} finally {
			isLoading.value = false
		}
	}

	async function fetchMailboxes() {
		if (!account.value) return
		try {
			const data = await api.call<MailboxData[]>('mail.api.mail.get_mailboxes', {
				account: account.value,
			})
			mailboxes.value = data
		} catch {
			mailboxes.value = []
		}
	}

	function resolveAccount(accounts?: UserAccount[]) {
		if (!accounts?.length) return

		const localId = ApplicationSettings.getString(ACCOUNT_STORAGE_KEY, '')
		if (localId && accounts.some((a) => a.id === localId)) {
			setAccount(localId)
			return
		}

		const personalId = accounts.find((a) => a.is_personal)?.id
		if (personalId) setAccount(personalId)
	}

	function setAccount(id: string) {
		accountId.value = id
		ApplicationSettings.setString(ACCOUNT_STORAGE_KEY, id)
		fetchMailboxes()
	}

	function reset() {
		user.value = null
		accountId.value = ''
		mailboxes.value = []
		ApplicationSettings.remove(ACCOUNT_STORAGE_KEY)
	}

	return {
		user,
		accountId,
		account,
		mailboxes,
		mailboxIds,
		isLoading,
		error,
		fetchUser,
		fetchMailboxes,
		setAccount,
		reset,
	}
})
