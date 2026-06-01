// Orchestrates the OAuth2 Authorization Code + PKCE login using an in-app WebView.
// The WebView (OAuthWebView.vue) loads Frappe's authorize page and intercepts the
// redirect back to com.frappe.mail://oauth, returning the code + state.

import { $showModal } from 'nativescript-vue'

import {
	type OAuthTokens,
	type RedirectResult,
	buildAuthorizeUrl,
	exchangeCodeForTokens,
} from '@/utils/oauth'
import { createPkcePair } from '@/utils/pkce'
import OAuthWebView from '@/components/OAuthWebView.vue'

export async function loginWithOAuth(siteUrl: string, clientId: string): Promise<OAuthTokens> {
	const pkce = createPkcePair()
	const authorizeUrl = buildAuthorizeUrl(siteUrl, clientId, pkce.codeChallenge, pkce.state)

	const result = await $showModal<RedirectResult | null>(OAuthWebView, {
		props: { authorizeUrl },
		fullscreen: true,
	})

	if (!result) throw new Error('Login cancelled')
	if (result.error) throw new Error(result.error)
	if (!result.code) throw new Error('No authorization code returned')
	if (result.state !== pkce.state) throw new Error('State mismatch — login aborted')

	return exchangeCodeForTokens(siteUrl, clientId, result.code, pkce.codeVerifier)
}
