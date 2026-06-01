import { computed, ref } from 'vue'
import { ApplicationSettings } from '@nativescript/core'
import { defineStore } from 'pinia'

const sessionKey = (siteUrl: string) => `mail-session:${siteUrl}`

export const sessionStore = defineStore('mail-session', () => {
	const loggedIn = ref(false)

	const isLoggedIn = computed(() => loggedIn.value)

	function loadSession(siteUrl: string) {
		loggedIn.value = ApplicationSettings.getBoolean(sessionKey(siteUrl), false)
	}

	async function login(siteUrl: string, usr: string, pwd: string): Promise<void> {
		const res = await fetch(`${siteUrl}/api/method/login`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
			body: JSON.stringify({ usr, pwd }),
		})
		const json = await res.json().catch(() => ({}))
		if (!res.ok || json.message === 'Failed') {
			throw new Error(json.message || 'Login failed')
		}
		loggedIn.value = true
		ApplicationSettings.setBoolean(sessionKey(siteUrl), true)
	}

	async function logout(siteUrl: string): Promise<void> {
		try {
			await fetch(`${siteUrl}/api/method/logout`, { method: 'POST' })
		} catch {
			// ignore network errors on logout
		}
		loggedIn.value = false
		ApplicationSettings.setBoolean(sessionKey(siteUrl), false)
	}

	return { isLoggedIn, loadSession, login, logout }
})
