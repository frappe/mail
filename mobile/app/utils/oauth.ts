// OAuth2 Authorization Code + PKCE protocol helpers against Frappe's OAuth provider.
// Endpoints (confirmed in frappe/integrations/oauth2.py):
//   authorize  GET  /api/method/frappe.integrations.oauth2.authorize
//   token      POST /api/method/frappe.integrations.oauth2.get_token   (form-encoded)

// Custom URL scheme registered in App_Resources (iOS Info.plist + Android manifest).
export const REDIRECT_URI = 'com.frappe.mail://oauth'
export const SCOPE = 'all openid'

const AUTHORIZE_PATH = '/api/method/frappe.integrations.oauth2.authorize'
const TOKEN_PATH = '/api/method/frappe.integrations.oauth2.get_token'

export interface OAuthTokens {
	access_token: string
	refresh_token: string
	expires_at: number // unix ms
}

// Parsed query params from the redirect back to REDIRECT_URI.
export interface RedirectResult {
	code?: string
	state?: string
	error?: string
}

function formEncode(params: Record<string, string>): string {
	return Object.keys(params)
		.map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
		.join('&')
}

export function buildAuthorizeUrl(
	siteUrl: string,
	clientId: string,
	codeChallenge: string,
	state: string,
): string {
	const query = formEncode({
		client_id: clientId,
		response_type: 'code',
		redirect_uri: REDIRECT_URI,
		scope: SCOPE,
		code_challenge: codeChallenge,
		code_challenge_method: 'S256',
		state,
	})
	return `${siteUrl}${AUTHORIZE_PATH}?${query}`
}

async function postToken(siteUrl: string, body: Record<string, string>): Promise<OAuthTokens> {
	const res = await fetch(`${siteUrl}${TOKEN_PATH}`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/x-www-form-urlencoded',
			Accept: 'application/json',
		},
		body: formEncode(body),
	})

	const json = await res.json().catch(() => ({}))

	if (!res.ok || json.error) {
		throw new Error(
			json.error_description || json.error || `Token request failed (${res.status})`,
		)
	}

	return {
		access_token: json.access_token,
		refresh_token: json.refresh_token,
		// Frappe returns expires_in (seconds); fall back to 1h if absent.
		expires_at: Date.now() + (json.expires_in ?? 3600) * 1000,
	}
}

export function exchangeCodeForTokens(
	siteUrl: string,
	clientId: string,
	code: string,
	codeVerifier: string,
): Promise<OAuthTokens> {
	return postToken(siteUrl, {
		grant_type: 'authorization_code',
		code,
		redirect_uri: REDIRECT_URI,
		client_id: clientId,
		code_verifier: codeVerifier,
	})
}

export function refreshTokens(
	siteUrl: string,
	clientId: string,
	refreshToken: string,
): Promise<OAuthTokens> {
	return postToken(siteUrl, {
		grant_type: 'refresh_token',
		refresh_token: refreshToken,
		client_id: clientId,
	})
}
