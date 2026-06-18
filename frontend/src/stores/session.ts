import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'

import router from '@/router'
import { raiseToast } from '@/utils'
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

	// Called when a request fails with an auth/permission error. Returns true if the session
	// is actually gone (so the caller can swallow the error and avoid a duplicate toast),
	// false if the session is still alive — i.e. a genuine PermissionError that should surface
	// normally. Frappe resets the user_id cookie to Guest on a dead session, so the cookie is
	// the discriminator. Signs out + notifies + redirects once; later concurrent calls just
	// report handled.
	const handleSessionExpired = (): boolean => {
		// Still logged in — this is a real permission error, not a logout.
		if (sessionUser()) return false

		if (user.value) {
			user.value = null
			userResource.reset()
			mailboxes.reset()
			raiseToast(__('You have been signed out. Please sign in again.'), 'error')
			if (!router.currentRoute.value.meta?.isLogin) router.replace({ name: 'Login' })
		}

		return true
	}

	return { isLoggedIn, login, logout, branding, handleSessionExpired }
})
