import type { NativeScriptConfig } from '@nativescript/core'

export default {
	id: 'com.frappe.mail',
	appPath: 'app',
	appResourcesPath: 'App_Resources',
	webpackConfigPath: 'webpack.config.cjs',
	android: {
		v8Flags: '--expose_gc',
		markingMode: 'none',
	},
} satisfies NativeScriptConfig
