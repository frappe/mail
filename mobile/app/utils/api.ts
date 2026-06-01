import { sessionStore } from '@/stores/session'
import { siteStore } from '@/stores/site'

export interface ApiError {
	message: string
	exc_type?: string
	status: number
}

// Wraps a Frappe API call: POST /api/method/<method> with JSON params.
// Injects a valid Bearer token (refreshing if expired) and retries once on 401.
export function useApi() {
	async function call<T>(method: string, params?: Record<string, unknown>): Promise<T> {
		const site = siteStore()
		const session = sessionStore()

		if (!site.activeSite) throw new Error('No active site')
		const { url: siteUrl, client_id } = site.activeSite

		const url = `${siteUrl}/api/method/${method}`
		const body = params ? JSON.stringify(params) : undefined
		const headers: Record<string, string> = {
			'Content-Type': 'application/json',
			Accept: 'application/json',
		}

		const token = await session.getValidAccessToken(siteUrl, client_id)
		if (token) headers['Authorization'] = `Bearer ${token}`

		let res = await fetch(url, { method: 'POST', headers, body })

		// The token may have been revoked server-side; refresh once and retry.
		if (res.status === 401 && (await session.refresh(siteUrl, client_id))) {
			headers['Authorization'] = `Bearer ${session.tokens?.access_token}`
			res = await fetch(url, { method: 'POST', headers, body })
		}

		const json = await res.json().catch(() => ({}))

		if (!res.ok) {
			const err: ApiError = {
				message: json?.message ?? json?.exc ?? `HTTP ${res.status}`,
				exc_type: json?.exc_type,
				status: res.status,
			}
			throw err
		}

		// Frappe wraps successful responses in { message: <data> }
		return json.message as T
	}

	async function unauthenticatedCall<T>(
		siteUrl: string,
		method: string,
		params?: Record<string, unknown>,
	): Promise<T> {
		const url = `${siteUrl}/api/method/${method}`
		const res = await fetch(url, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
			body: params ? JSON.stringify(params) : undefined,
		})

		const json = await res.json().catch(() => ({}))

		if (!res.ok) {
			throw {
				message: json?.message ?? `HTTP ${res.status}`,
				status: res.status,
			} as ApiError
		}

		return json.message as T
	}

	return { call, unauthenticatedCall }
}
