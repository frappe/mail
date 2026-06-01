declare module '*.vue' {
	import type { DefineComponent } from 'vue'

	const component: DefineComponent
	export default component
}

declare const __: (message: string, variables?: string[]) => string

declare module '@vue/runtime-core' {
	interface ComponentCustomProperties {
		__(message: string, variables?: string[]): string
	}
}
