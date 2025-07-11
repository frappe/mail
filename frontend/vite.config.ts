import path from 'path'

import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vitejs.dev/config/
export default defineConfig({
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
						'email_message',
						'mail_tenant',
						'mail_tenant_member',
						'mail_domain',
						'mail_domain_request',
						'mail_alias',
						'mailing_list',
						'mailing_list_member',
						'mail_account',
						'mail_account_request',
						'mail_contact',
						'mail_recipient',
						'mail_settings',
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
			devOptions: {
				enabled: true,
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
				theme_color: '#FFF',
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
		alias: {
			'@': path.resolve(__dirname, 'src'),
		},
	},
	optimizeDeps: {
		include: [
			'frappe-ui > feather-icons',
			'showdown',
			'engine.io-client',
			'prosemirror-state',
			'prosemirror-view',
			'highlight.js/lib/core',
		],
	},
})
