// Module augmentation for Vue's ComponentCustomProperties.
// Must be in a module file (export {}) so TypeScript merges this into
// @vue/runtime-core's existing exports rather than replacing them.
export {}

declare module '@vue/runtime-core' {
	interface ComponentCustomProperties {
		__(message: string, variables?: string[]): string
	}
}
