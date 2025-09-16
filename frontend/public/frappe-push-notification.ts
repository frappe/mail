import { initializeApp } from 'firebase/app'
import {
	type Messaging,
	deleteToken,
	getMessaging,
	getToken,
	isSupported,
	onMessage as onFCMMessage,
} from 'firebase/messaging'

// FCM web config to initialize firebase app
type WebConfigType = {
	projectId: string
	appId: string
	apiKey: string
	authDomain: string
	messagingSenderId: string
}

type MessagePayload = {
	data: {
		title: string
		body: string
		click_action: string | null
		notification_icon?: string
	}
}

type OnMessageCallback = (payload: MessagePayload) => void

class FrappePushNotification {
	static get relayServerBaseURL(): string {
		return window.push_relay_server_url
	}

	// client info
	projectName: string
	webConfig: WebConfigType | null
	vapidPublicKey: string
	token: string | null

	// state
	initialized: boolean
	messaging: Messaging | null
	serviceWorkerRegistration: ServiceWorkerRegistration | null

	// event handlers
	onMessageHandler: OnMessageCallback | null

	constructor(projectName: string) {
		// client info
		this.projectName = projectName
		this.webConfig = null
		this.vapidPublicKey = ''
		this.token = null

		// state
		this.initialized = false
		this.messaging = null
		this.serviceWorkerRegistration = null

		// event handlers
		this.onMessageHandler = null
	}

	// Initialize notification service client
	async initialize(serviceWorkerRegistration: ServiceWorkerRegistration): Promise<void> {
		if (this.initialized) return

		this.serviceWorkerRegistration = serviceWorkerRegistration
		const config = await this.fetchWebConfig()
		this.messaging = getMessaging(initializeApp(config))
		this.onMessage(this.onMessageHandler)
		this.initialized = true
	}

	// Append config to service worker URL
	async appendConfigToServiceWorkerURL(url: string, parameter_name = 'config'): Promise<string> {
		const config = await this.fetchWebConfig()
		const encode_config = encodeURIComponent(JSON.stringify(config))
		return `${url}?${parameter_name}=${encode_config}`
	}

	// Fetch web config of the project
	async fetchWebConfig(): Promise<WebConfigType> {
		if (this.webConfig !== null && this.webConfig !== undefined) return this.webConfig

		const url = `${FrappePushNotification.relayServerBaseURL}/api/method/notification_relay.api.get_config?project_name=${this.projectName}`
		const response = await fetch(url)
		const response_json = await response.json()
		this.webConfig = response_json.config
		return this.webConfig!
	}

	// Fetch VAPID public key
	async fetchVapidPublicKey(): Promise<string> {
		if (this.vapidPublicKey !== '') return this.vapidPublicKey

		const url = `${FrappePushNotification.relayServerBaseURL}/api/method/notification_relay.api.get_config?project_name=${this.projectName}`
		const response = await fetch(url)
		const response_json = await response.json()
		this.vapidPublicKey = response_json.vapid_public_key
		return this.vapidPublicKey
	}

	// Register on message handler
	onMessage(callback: OnMessageCallback | null): void {
		if (callback == null) return
		this.onMessageHandler = callback
		if (this.messaging == null) return
		onFCMMessage(this.messaging, this.onMessageHandler)
	}

	// Check if notification is enabled
	isNotificationEnabled() {
		return localStorage.getItem(`firebase_token_${this.projectName}`) !== null
	}

	// This will return notification permission status and token
	async enableNotification(): Promise<{ permission_granted: boolean; token: string }> {
		if (!(await isSupported()))
			throw new Error('Push notifications are not supported on your device')

		// Return if token already presence in the instance
		if (this.token != null) return { permission_granted: true, token: this.token }

		// ask for permission
		const permission = await Notification.requestPermission()
		if (permission !== 'granted') return { permission_granted: false, token: '' }

		// check in local storage for old token
		const oldToken = localStorage.getItem(`firebase_token_${this.projectName}`)
		const vapidKey = await this.fetchVapidPublicKey()
		const newToken = await getToken(this.messaging!, {
			vapidKey: vapidKey,
			serviceWorkerRegistration: this.serviceWorkerRegistration!,
		})
		// register new token if token is changed
		if (oldToken !== newToken) {
			// unsubscribe old token
			if (oldToken) await this.unregisterTokenHandler(oldToken)

			// subscribe push notification and register token
			const isSubscriptionSuccessful = await this.registerTokenHandler(newToken)
			if (isSubscriptionSuccessful === false)
				throw new Error('Failed to subscribe to push notification')

			// save token to local storage
			localStorage.setItem(`firebase_token_${this.projectName}`, newToken)
		}
		this.token = newToken
		return { permission_granted: true, token: newToken }
	}

	// This will delete token from firebase and unsubscribe from push notification
	async disableNotification(): Promise<void> {
		if (this.token == null)
			// try to fetch token from local storage
			this.token = localStorage.getItem(`firebase_token_${this.projectName}`)
		if (this.token == null || this.token === '') return

		// delete old token from firebase
		try {
			await deleteToken(this.messaging!)
		} catch (e) {
			console.error('Failed to delete token from firebase')
			console.error(e)
		}
		try {
			await this.unregisterTokenHandler(this.token)
		} catch (e) {
			console.error('Failed to unsubscribe from push notification')
			console.error(e)
		}
		// remove token
		localStorage.removeItem(`firebase_token_${this.projectName}`)
		this.token = null
	}

	// Register Token Handler
	async registerTokenHandler(token: string): Promise<boolean> {
		try {
			const response = await fetch(
				'/api/method/frappe.push_notification.subscribe?fcm_token=' +
					token +
					'&project_name=' +
					this.projectName,
				{
					method: 'GET',
					headers: { 'Content-Type': 'application/json' },
				},
			)
			return response.status === 200
		} catch (e) {
			console.error(e)
			return false
		}
	}

	// Unregister Token Handler
	async unregisterTokenHandler(token: string): Promise<boolean> {
		try {
			const response = await fetch(
				'/api/method/frappe.push_notification.unsubscribe?fcm_token=' +
					token +
					'&project_name=' +
					this.projectName,
				{
					method: 'GET',
					headers: {
						'Content-Type': 'application/json',
					},
				},
			)
			return response.status === 200
		} catch (e) {
			console.error(e)
			return false
		}
	}
}

export default FrappePushNotification
