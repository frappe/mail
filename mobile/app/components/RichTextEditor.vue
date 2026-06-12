<template>
	<WebView :src="doc" @loaded="onLoaded" @loadStarted="onLoadStarted" />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { isAndroid } from '@nativescript/core'

import { buildEditorDocument } from '@/utils/richTextDoc'

import type { EventData, LoadEventData } from '@nativescript/core'

const props = defineProps<{ modelValue: string; placeholder?: string }>()
const emit = defineEmits<{ 'update:modelValue': [html: string] }>()

// Built once with the initial content baked in. We deliberately do NOT rebind
// `src` to modelValue — re-setting it would reload the WebView and drop the
// caret/selection on every keystroke. The contenteditable is the source of
// truth after mount; it streams changes back out via the x-rt scheme.
const doc = ref(buildEditorDocument(props.modelValue || '', props.placeholder || ''))

function onLoadStarted(args: LoadEventData) {
	const url = args.url ?? ''
	// The editor streams its HTML out via a hidden iframe navigating to x-rt-sync:.
	if (!url.startsWith('x-rt-sync:')) return
	const view = args.object as unknown as { stopLoading?: () => void }
	view.stopLoading?.()
	emit('update:modelValue', decodeURIComponent(url.slice('x-rt-sync:'.length)))
}

function onLoaded(args: EventData) {
	if (!isAndroid) return
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const native = (args.object as any).android
	// Make the WebView focusable so tapping the contenteditable brings up the
	// soft keyboard, and render on a software layer to avoid the Android white
	// flash during the page transition (mirrors ThreadView).
	native?.setFocusable?.(true)
	native?.setFocusableInTouchMode?.(true)
	native?.setLayerType?.(1, null)
}
</script>
