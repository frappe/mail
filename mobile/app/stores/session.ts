import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { ApplicationSettings } from '@nativescript/core'

// Token storage key is namespaced by site URL so multi-site works cleanly.
// NOTE: ApplicationSettings is not encrypted — issue #486 (auth implementation)
// replaces this with secure storage when wiring the real OAuth2 PKCE flow.

function tokenKey(siteUrl: string) {
	return `mail-token:${siteUrl}`
}

export interface OAuthTokens {
	access_token: string
	refresh_token: string
	expires_at: number // unix ms
}

export const sessionStore = defineStore('mail-session', () => {
	const siteUrl = ref<string>('')
	const tokens = ref<OAuthTokens | null>(null)

	const isLoggedIn = computed(() => !!tokens.value?.access_token)

	function loadTokens(site: string) {
		siteUrl.value = site
		try {
			const raw = ApplicationSettings.getString(tokenKey(site), '')
			tokens.value = raw ? (JSON.parse(raw) as OAuthTokens) : null
		} catch {
			tokens.value = null
		}
	}

	function saveTokens(site: string, t: OAuthTokens) {
		siteUrl.value = site
		tokens.value = t
		ApplicationSettings.setString(tokenKey(site), JSON.stringify(t))
	}

	function clearTokens(site: string) {
		tokens.value = null
		ApplicationSettings.remove(tokenKey(site))
	}

	function isTokenExpired(): boolean {
		if (!tokens.value) return true
		return Date.now() >= tokens.value.expires_at - 60_000 // 1 min buffer
	}

	return { siteUrl, tokens, isLoggedIn, loadTokens, saveTokens, clearTokens, isTokenExpired }
})
