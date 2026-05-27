import js from '@eslint/js'
import globals from 'globals'
import tseslint from 'typescript-eslint'
import pluginVue from 'eslint-plugin-vue'
import vueParser from 'vue-eslint-parser'
import prettier from 'eslint-plugin-prettier'
import eslintConfigPrettier from 'eslint-config-prettier'

export default [
	{ ignores: ['platforms/', 'hooks/', '*.js'] },
	js.configs.recommended,
	...tseslint.configs.recommended,
	...pluginVue.configs['flat/recommended'],
	eslintConfigPrettier,
	{
		files: ['app/**/*.{ts,vue}'],
		languageOptions: {
			parser: vueParser,
			parserOptions: {
				parser: tseslint.parser,
				extraFileExtensions: ['.vue'],
				sourceType: 'module',
			},
			globals: { ...globals.node },
		},
		plugins: { prettier },
		rules: {
			'prettier/prettier': 'error',
			'vue/multi-word-component-names': 'off',
			'@typescript-eslint/no-explicit-any': 'warn',
		},
	},
]
