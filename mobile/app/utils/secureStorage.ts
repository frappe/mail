// Encrypted, per-site token storage backed by the platform keystore
// (iOS Keychain / Android Keystore) via @nativescript/secure-storage.
// Replaces the unencrypted ApplicationSettings used in the #484 scaffold.

import { SecureStorage } from '@nativescript/secure-storage'

import type { OAuthTokens } from '@/utils/oauth'

const storage = new SecureStorage()

// Namespaced by site URL so multiple sites store tokens independently.
const tokenKey = (siteUrl: string) => `mail-token:${siteUrl}`

export function saveTokens(siteUrl: string, tokens: OAuthTokens): void {
	storage.setSync({ key: tokenKey(siteUrl), value: JSON.stringify(tokens) })
}

export function loadTokens(siteUrl: string): OAuthTokens | null {
	const raw = storage.getSync({ key: tokenKey(siteUrl) })
	if (!raw) return null
	try {
		return JSON.parse(raw) as OAuthTokens
	} catch {
		return null
	}
}

export function clearTokens(siteUrl: string): void {
	storage.removeSync({ key: tokenKey(siteUrl) })
}
