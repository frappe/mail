<template>
	<WebView :src="doc" @loaded="onLoaded" @loadStarted="onLoadStarted" />
</template>

<script setup lang="ts">
/* global android */
import { onUnmounted, ref } from 'vue'
import { isAndroid } from '@nativescript/core'

import { buildEditorDocument } from '@/utils/richTextDoc'

import type { EventData, LoadEventData } from '@nativescript/core'

const props = defineProps<{ modelValue: string; placeholder?: string }>()
const emit = defineEmits<{ 'update:modelValue': [html: string] }>()

// Built once with the initial content baked in. We deliberately do NOT rebind
// `src` to modelValue — re-setting it would reload the WebView and drop the
// caret/selection on every keystroke. The contenteditable is the source of
// truth after mount; native PULLS its HTML via evaluateJavascript (see
// getHtml) — navigation-based messaging is unusable here: NativeScript's
// Android WebView tries to start an Activity for any custom-scheme navigation
// and the aborted navigation kills the document.
const doc = ref(buildEditorDocument(props.modelValue || '', props.placeholder || ''))

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let webView: any = null

function onLoadStarted(args: LoadEventData) {
	const url = args.url ?? ''
	// Keep the document alive: swallow any navigation away from it (e.g. a tap
	// on a link inside pasted/quoted content).
	if (/^(https?:|x-)/i.test(url)) {
		;(args.object as unknown as { stopLoading?: () => void }).stopLoading?.()
	}
}

// Reads the editor's current HTML out of the WebView. Resolves null when the
// editor isn't ready (callers skip the update rather than wiping content).
function getHtml(): Promise<string | null> {
	return new Promise((resolve) => {
		const js = "document.getElementById('e') ? document.getElementById('e').innerHTML : null"
		// Don't let a missing callback hang callers (e.g. while navigating away).
		const bail = setTimeout(() => resolve(null), 400)
		const done = (value: string | null) => {
			clearTimeout(bail)
			resolve(value)
		}
		try {
			if (isAndroid) {
				webView?.android?.evaluateJavascript(
					js,
					new android.webkit.ValueCallback({
						onReceiveValue: (value: string) => {
							try {
								done(value && value !== 'null' ? JSON.parse(value) : null)
							} catch {
								done(null)
							}
						},
					}),
				)
			} else {
				webView?.ios?.evaluateJavaScriptCompletionHandler(js, (result: unknown) =>
					done(typeof result === 'string' ? result : null),
				)
			}
		} catch {
			done(null)
		}
	})
}

defineExpose({ getHtml })

// Keep v-model loosely in sync for autosave: poll the editor and emit when the
// content changed. (Exact-on-demand reads go through getHtml before save/send.)
const poll = setInterval(async () => {
	const html = await getHtml()
	if (html !== null && html !== props.modelValue) emit('update:modelValue', html)
}, 2000)
onUnmounted(() => clearInterval(poll))

// NativeScript dismisses the IME 10ms after an EditText blurs to a
// non-EditText (editable-text-base/index.android.js). The WebView's focus-gain
// fires synchronously in the same focus transfer — before that timer can run —
// so cancelling it keeps the keyboard open through the handoff (exactly what
// core does for EditText→EditText). The stale timer id is harmless: core's
// next dismiss clears and re-arms it.
function cancelPendingKeyboardDismiss() {
	try {
		// eslint-disable-next-line @typescript-eslint/no-require-imports
		const etb = require('@nativescript/core/ui/editable-text-base')
		if (etb.dismissKeyboardTimeoutId) clearTimeout(etb.dismissKeyboardTimeoutId)
	} catch {
		// best-effort
	}
}

// Fallback for when the keyboard was genuinely closed: force it open once the
// focus transfer settles (a no-op when it's already up).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function forceAndroidKeyboard(wv: any) {
	if (!isAndroid || !wv) return
	setTimeout(() => {
		try {
			wv.requestFocus()
			// Context.INPUT_METHOD_SERVICE === 'input_method'
			const imm = wv.getContext().getSystemService('input_method')
			// SHOW_FORCED (2) — SHOW_IMPLICIT is ignored for the WebView here.
			imm.showSoftInput(wv, 2)
		} catch {
			// best-effort
		}
	}, 120)
}

function onLoaded(args: EventData) {
	webView = args.object
	if (!isAndroid) return
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const native = (args.object as any).android
	// Make the WebView focusable so tapping the contenteditable brings up the
	// soft keyboard. Deliberately NOT on a software layer (unlike the read-only
	// ThreadView): a software-layered WebView caches its bitmap and doesn't
	// reliably re-rasterize as editable content changes — typed text lands in
	// the DOM but never paints.
	native?.setFocusable?.(true)
	native?.setFocusableInTouchMode?.(true)

	// When the WebView gains focus (e.g. tapping the body while a native field's
	// keyboard is up), force the soft keyboard — the field's IME-hide otherwise
	// wins the handoff and the keyboard never re-appears.
	try {
		native?.setOnFocusChangeListener?.(
			new android.view.View.OnFocusChangeListener({
				onFocusChange(view: unknown, hasFocus: boolean) {
					if (!hasFocus) return
					cancelPendingKeyboardDismiss() // keep the keyboard from closing at all
					forceAndroidKeyboard(view) // and reopen it if it was already closed
				},
			}),
		)
	} catch {
		// best-effort
	}
}
</script>
