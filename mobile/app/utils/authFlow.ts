// Orchestrates the OAuth2 Authorization Code + PKCE login using the system
// browser (ASWebAuthenticationSession on iOS, Chrome Custom Tabs on Android via
// nativescript-inappbrowser). The browser handles the redirect back to
// com.frappe.mail://oauth — registered as a deep link in Info.plist / the
// Android manifest — and openAuth resolves with that callback URL.
//
// This replaces the in-app WebView, which couldn't reliably intercept the custom
// redirect scheme on Android and produced post-login white screens on iOS.

import { InAppBrowser } from 'nativescript-inappbrowser'

import {
	type OAuthTokens,
	REDIRECT_URI,
	type RedirectResult,
	buildAuthorizeUrl,
	exchangeCodeForTokens,
} from '@/utils/oauth'
import { createPkcePair } from '@/utils/pkce'

export async function loginWithOAuth(siteUrl: string, clientId: string): Promise<OAuthTokens> {
	const pkce = createPkcePair()
	const authorizeUrl = buildAuthorizeUrl(siteUrl, clientId, pkce.codeChallenge, pkce.state)

	const result = await InAppBrowser.openAuth(authorizeUrl, REDIRECT_URI, {
		// iOS: share cookies with Safari so an existing site session is reused.
		ephemeralWebSession: false,
		// Android: a leaner tab chrome for the auth handoff.
		showTitle: false,
		enableUrlBarHiding: true,
		enableDefaultShare: false,
	})

	if (result.type !== 'success' || !result.url) throw new Error('Login cancelled')

	const redirect = parseRedirect(result.url)
	if (redirect.error) throw new Error(redirect.error)
	if (!redirect.code) throw new Error('No authorization code returned')
	if (redirect.state !== pkce.state) throw new Error('State mismatch — login aborted')

	return exchangeCodeForTokens(siteUrl, clientId, redirect.code, pkce.codeVerifier)
}

function parseRedirect(url: string): RedirectResult {
	const query = url.split('?')[1] || ''
	const params: Record<string, string> = {}
	for (const pair of query.split('&')) {
		const [k, v] = pair.split('=')
		if (k) params[decodeURIComponent(k)] = decodeURIComponent(v || '')
	}
	return { code: params.code, state: params.state, error: params.error }
}
