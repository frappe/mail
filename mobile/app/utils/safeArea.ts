// Status-bar inset (in device-independent pixels). Android draws edge-to-edge
// (enforced on Android 15+), so the top bar must be pushed below the status bar
// / camera cutout. On iOS NativeScript already insets page content, so 0.

import { Utils, isAndroid } from '@nativescript/core'

function androidDimen(name: string): number {
	if (!isAndroid) return 0
	const resources = Utils.android.getApplicationContext().getResources()
	const id = resources.getIdentifier(name, 'dimen', 'android')
	if (id <= 0) return 0
	return Utils.layout.toDeviceIndependentPixels(resources.getDimensionPixelSize(id))
}

export function safeAreaTop(): number {
	return androidDimen('status_bar_height')
}

export function safeAreaBottom(): number {
	return androidDimen('navigation_bar_height')
}
