import type { NotificationPayload } from '@/types'

export const isChrome = (): boolean => navigator.userAgent.toLowerCase().includes('chrome')

export const showNotification = (payload: NotificationPayload): void => {
	const registration: ServiceWorkerRegistration | undefined =
		window.frappePushNotification?.serviceWorkerRegistration
	if (!registration) return

	const notificationTitle = payload?.data?.title
	const notificationOptions: NotificationOptions = {
		body: payload?.data?.body || '',
		badge: '/assets/mail/frontend/logo-96-96.png',
	}
	if (payload?.data?.notification_icon)
		notificationOptions['icon'] = payload.data.notification_icon

	if (isChrome()) notificationOptions['data'] = { url: payload?.data?.click_action }
	else if (payload?.data?.click_action)
		notificationOptions['actions'] = [
			{ action: payload.data.click_action, title: 'View Details' },
		]

	registration.showNotification(notificationTitle || '', notificationOptions)
}
