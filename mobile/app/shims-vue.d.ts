// Ambient declarations only — no top-level import/export (wildcard module
// declarations like '*.vue' must live in a non-module ambient file).

declare module '*.vue' {
	import type { DefineComponent } from 'vue'

	const component: DefineComponent
	export default component
}

// __ is defined in utils/translation and installed as a global via the plugin.
declare const __: (message: string, variables?: string[]) => string
