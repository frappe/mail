import { useApi } from '@/utils/api'
import { sessionStore } from '@/stores/session'
import { siteStore } from '@/stores/site'

let translatedMessages: Record<string, string> = {}

type TranslationGlobal = typeof globalThis & {
	__: typeof __
}

export function __(message: string, variables?: string[]) {
	const translatedMessage = translatedMessages[message] || message
	const hasPlaceholders = /{\d+}/.test(message) && variables

	if (!hasPlaceholders) return translatedMessage

	return translatedMessage.replace(/{(\d+)}/g, (match: string, index: string) => {
		const variable = variables[Number(index)]
		return typeof variable !== 'undefined' ? variable : match
	})
}

;(globalThis as TranslationGlobal).__ = __

export async function loadTranslations() {
	const site = siteStore()
	if (!site.activeSite) {
		translatedMessages = {}
		return
	}

	const { call, unauthenticatedCall } = useApi()

	try {
		translatedMessages = sessionStore().isLoggedIn
			? await call<Record<string, string>>('mail.api.get_translations')
			: await unauthenticatedCall<Record<string, string>>(
					site.activeSite.url,
					'mail.api.get_translations',
				)
	} catch {
		translatedMessages = {}
	}
}

export default {
	install(app: { config: { globalProperties: Record<string, unknown> } }) {
		app.config.globalProperties.__ = __
		;(globalThis as TranslationGlobal).__ = __
	},
}
