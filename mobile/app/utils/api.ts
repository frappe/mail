import { siteStore } from '@/stores/site'
import { sessionStore } from '@/stores/session'

export interface ApiError {
	message: string
	exc_type?: string
	status: number
}

// Wraps a Frappe API call: POST /api/method/<method> with JSON params.
// Handles Authorization header injection and surfaces Frappe error shapes.
export function useApi() {
	async function call<T>(method: string, params?: Record<string, unknown>): Promise<T> {
		const site = siteStore()
		const session = sessionStore()

		if (!site.activeSite) throw new Error('No active site')

		const url = `${site.activeSite.url}/api/method/${method}`
		const headers: Record<string, string> = {
			'Content-Type': 'application/json',
			Accept: 'application/json',
		}

		if (session.tokens?.access_token) {
			headers['Authorization'] = `Bearer ${session.tokens.access_token}`
		}

		const res = await fetch(url, {
			method: 'POST',
			headers,
			body: params ? JSON.stringify(params) : undefined,
		})

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
