import './index.css'

import { createApp } from 'vue'
import { spritePlugin } from 'frappe-ui/icons'
import { createPinia } from 'pinia'
import { frappeRequest, pageMetaPlugin, setConfig } from 'frappe-ui'

import App from '@/App.vue'
import router from '@/router'
import { initSocket } from '@/socket'
import translationPlugin from '@/translation'
import dayjs from '@/utils/dayjs'
import { sessionStore } from '@/stores/session'
import { userStore } from '@/stores/user'

import FrappePushNotification from '../public/frappe-push-notification'

// Centralised auth handling: when a request comes back unauthenticated, sign the user out and
// redirect to login so they can't keep acting against a dead session. The error is always
// re-thrown afterwards, so the originating resource still reports it normally (no swallowing,
// which previously left resources hanging and hid errors like a wrong-password login).
setConfig('resourceFetcher', async (options: Parameters<typeof frappeRequest>[0]) => {
	try {
		return await frappeRequest(options)
	} catch (error) {
		const excType = (error as { exc_type?: string })?.exc_type
		if (excType === 'AuthenticationError' || excType === 'PermissionError')
			sessionStore().handleSessionExpired()
		throw error
	}
})

const app = createApp(App)
app.use(router)
app.use(createPinia())
app.use(translationPlugin)
app.use(pageMetaPlugin)
app.use(spritePlugin)

const { userResource } = userStore()
app.provide('$user', userResource)
app.provide('$dayjs', dayjs)
app.provide('$socket', initSocket())

const registerServiceWorker = async () => {
	if (!('serviceWorker' in navigator))
		return console.error('Service worker not enabled/supported by the browser')

	window.frappePushNotification = new FrappePushNotification('mail')
	let serviceWorkerURL = '/assets/mail/frontend/sw.js'
	let config = ''

	try {
		config = await window.frappePushNotification.fetchWebConfig()
		serviceWorkerURL = `${serviceWorkerURL}?config=${encodeURIComponent(JSON.stringify(config))}`
	} catch (err) {
		console.error('Failed to fetch FCM config', err)
	}

	navigator.serviceWorker
		.register(serviceWorkerURL, { type: 'module' })
		.then((registration) => {
			if (config)
				window.frappePushNotification
					.initialize(registration)
					.then(() => console.log('Frappe Push Notification initialized'))
		})
		.catch((err) => console.error('Failed to register service worker', err))
}

router.isReady().then(async () => {
	// if (import.meta.env.DEV)
	// 	await frappeRequest({ url: '/api/method/mail.www.mail.get_context_for_dev' }).then(
	// 		(values) => Object.keys(values).forEach((key) => (window[key] = values[key])),
	// 	)

	registerServiceWorker()
	app.mount('#app')
})
