export {}

type TranslateFunction = (message: string, variables?: (string | number)[]) => string
declare global {
	const __: TranslateFunction
}
declare module 'vue' {
	interface ComponentCustomProperties {
		__: TranslateFunction
	}
}
