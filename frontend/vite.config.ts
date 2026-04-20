import fs from 'fs'
import path from 'path'

import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

const frappeUIPath = path.resolve(__dirname, '../frappe-ui/src/index.ts')

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
	define: {
		__VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false,
	},
	plugins: [
		frappeui({
			frappeProxy: true,
			lucideIcons: true,
			jinjaBootData: true,
			frappeTypes: {
				input: {
					frappe: ['file'],
					mail: [
						'mail_message',
						'mail_domain_request',
						'mail_account_request',
						'mail_contact',
						'mail_recipient',
						'mail_settings',
						'identity',
						'mail_signature',
						'vacation_response',
						'sieve_script',
					],
				},
			},
			buildConfig: {
				outDir: '../mail/public/frontend',
				baseUrl: '/assets/mail/frontend/',
				indexHtmlPath: '../mail/www/mail.html',
				emptyOutDir: true,
				sourcemap: true,
			},
		}),
		vue({
			script: {
				defineModel: true,
				propsDestructure: true,
			},
		}),
		VitePWA({
			registerType: 'autoUpdate',
			strategies: 'injectManifest',
			injectRegister: null,
			filename: 'sw.ts',
			injectManifest: {
				maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
			},
			devOptions: {
				enabled: true,
				type: 'module',
			},
			workbox: {
				cleanupOutdatedCaches: true,
				maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
			},
			manifest: {
				display: 'standalone',
				name: 'Frappe Mail',
				short_name: 'Frappe Mail',
				start_url: '/mail',
				description: 'Modern email client powered by Frappe',
				icons: [
					{
						src: '/assets/mail/frontend/manifest/manifest-icon-192.maskable.png',
						sizes: '192x192',
						type: 'image/png',
						purpose: 'any',
					},
					{
						src: '/assets/mail/frontend/manifest/manifest-icon-192.maskable.png',
						sizes: '192x192',
						type: 'image/png',
						purpose: 'maskable',
					},
					{
						src: '/assets/mail/frontend/manifest/manifest-icon-512.maskable.png',
						sizes: '512x512',
						type: 'image/png',
						purpose: 'any',
					},
					{
						src: '/assets/mail/frontend/manifest/manifest-icon-512.maskable.png',
						sizes: '512x512',
						type: 'image/png',
						purpose: 'maskable',
					},
				],
			},
		}),
	],
	resolve: {
		alias: [
			{ find: '@', replacement: path.resolve(__dirname, 'src') },
			...(fs.existsSync(frappeUIPath)
				? [{ find: /^frappe-ui$/, replacement: frappeUIPath }]
				: []),
		],
		dedupe: ['vue', 'prosemirror-state', 'prosemirror-view'],
	},
	optimizeDeps: {
		include: [
			'frappe-ui > feather-icons',
			'interactjs',
			'engine.io-client',
			'prosemirror-state',
			'prosemirror-view',
			'highlight.js/lib/core',
		],
		exclude: mode === 'production' ? [] : ['frappe-ui'],
	},
}))
