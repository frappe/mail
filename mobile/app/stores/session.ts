import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { loginWithOAuth } from '@/utils/authFlow'
import { type OAuthTokens, refreshTokens } from '@/utils/oauth'
import { clearTokens, loadTokens, saveTokens } from '@/utils/secureStorage'

export type { OAuthTokens }

// Tokens are persisted per site in the platform keystore (see utils/secureStorage).
export const sessionStore = defineStore('mail-session', () => {
	const tokens = ref<OAuthTokens | null>(null)

	const isLoggedIn = computed(() => !!tokens.value?.access_token)

	// Load the stored tokens for a site (e.g. on app start / site switch).
	function load(siteUrl: string) {
		tokens.value = loadTokens(siteUrl)
	}

	function isExpired(): boolean {
		if (!tokens.value) return true
		return Date.now() >= tokens.value.expires_at - 60_000 // 1 min buffer
	}

	// Run the full PKCE login for a site and persist the resulting tokens.
	async function login(siteUrl: string, clientId: string) {
		const t = await loginWithOAuth(siteUrl, clientId)
		tokens.value = t
		saveTokens(siteUrl, t)
	}

	// Silently refresh the access token. On failure, clears the session.
	async function refresh(siteUrl: string, clientId: string): Promise<boolean> {
		if (!tokens.value?.refresh_token) return false
		try {
			const t = await refreshTokens(siteUrl, clientId, tokens.value.refresh_token)
			tokens.value = t
			saveTokens(siteUrl, t)
			return true
		} catch {
			logout(siteUrl)
			return false
		}
	}

	function logout(siteUrl: string) {
		tokens.value = null
		clearTokens(siteUrl)
	}

	// Returns a usable access token, refreshing first if it is expired.
	async function getValidAccessToken(siteUrl: string, clientId: string): Promise<string | null> {
		if (!tokens.value) return null
		if (isExpired() && !(await refresh(siteUrl, clientId))) return null
		return tokens.value?.access_token ?? null
	}

	return { tokens, isLoggedIn, load, isExpired, login, refresh, logout, getValidAccessToken }
})
