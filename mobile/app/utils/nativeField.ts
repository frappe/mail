import { isAndroid } from '@nativescript/core'

import type { EventData } from '@nativescript/core'

// Removes Android's native EditText underline so our own row dividers are the
// only horizontal lines (iOS draws no underline, so this is a no-op there).
// Wire it to a TextField's @loaded.
export function flattenField(args: EventData) {
	if (!isAndroid) return
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const et = (args.object as any).android
	et?.setBackground?.(null)
}
