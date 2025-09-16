import './index.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { frappeRequest, pageMetaPlugin, setConfig } from 'frappe-ui'

import App from '@/App.vue'
import router from '@/router'
import { initSocket } from '@/socket'
import translationPlugin from '@/translation'
import dayjs from '@/utils/dayjs'
import { userStore } from '@/stores/user'

import FrappePushNotification from '../public/frappe-push-notification'

setConfig('resourceFetcher', frappeRequest)

const app = createApp(App)
app.use(router)
app.use(createPinia())
app.use(translationPlugin)
app.use(pageMetaPlugin)

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
	if (import.meta.env.DEV)
		await frappeRequest({ url: '/api/method/mail.www.mail.get_context_for_dev' }).then(
			async (values) => {
				if (!window.frappe) window.frappe = {}
				window.frappe.boot = values
			},
		)

	registerServiceWorker()
	app.mount('#app')
})
