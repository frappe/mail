import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'

import router from '@/router'
import { userStore } from '@/stores/user'

export const sessionStore = defineStore('mail-session', () => {
	const { userResource, reset } = userStore()

	const sessionUser = () => {
		const cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
		let _sessionUser = cookies.get('user_id')
		if (_sessionUser === 'Guest') _sessionUser = null

		return _sessionUser
	}

	const user = ref(sessionUser())
	const isLoggedIn = computed(() => !!user.value)

	const login = createResource({
		url: 'login',
		onError: () => {
			throw new Error('Invalid email or password')
		},
		onSuccess: () => {
			// Start from a clean slate: a prior session's account/resources may still be in memory
			// (e.g. cookies cleared without a page reload). Without this, resolveAccount() would
			// skip setAccount() and the mailboxes/account resources wouldn't load until a reload.
			reset()
			userResource.reload()
			user.value = sessionUser()
			login.reset()

			if (user.value === 'Administrator') window.location.replace('/app')
			else router.replace('/')
		},
	})

	const logout = createResource({
		url: 'logout',
		onSuccess() {
			reset()
			user.value = null
			window.location.reload()
		},
	})

	const branding = createResource({
		url: 'mail.api.get_branding',
		cache: 'brand',
		auto: true,
		onSuccess: (data) => (document.querySelector("link[rel='icon']").href = data.favicon),
	})

	return { isLoggedIn, login, logout, branding }
})
