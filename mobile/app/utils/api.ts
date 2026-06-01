import { siteStore } from '@/stores/site'

export interface ApiError {
	message: string
	exc_type?: string
	status: number
}

export function useApi() {
	async function call<T>(method: string, params?: Record<string, unknown>): Promise<T> {
		const site = siteStore()
		if (!site.activeSite) throw new Error('No active site')

		const url = `${site.activeSite.url}/api/method/${method}`
		const res = await fetch(url, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
			body: params ? JSON.stringify(params) : undefined,
		})

		const json = await res.json().catch(() => ({}))

		if (!res.ok) {
			throw {
				message: json?.message ?? json?.exc ?? `HTTP ${res.status}`,
				exc_type: json?.exc_type,
				status: res.status,
			} as ApiError
		}

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
