<template>
	<!-- Bottom sheet inside the compose page: scrim + slide-up panel. Mirrors
	     FilterSheet/AccountSheet, but lives over the compose Page (not the shell). -->
	<GridLayout :visibility="visible ? 'visible' : 'collapse'" rows="*, auto">
		<StackLayout
			rowSpan="2"
			class="bg-surface-gray-7"
			@loaded="onScrimLoaded"
			@tap="$emit('close')"
		/>

		<StackLayout
			row="1"
			class="bg-surface-white rounded-t-3xl pb-7"
			@loaded="onSheetLoaded"
			@tap="() => {}"
		>
			<StackLayout
				class="bg-surface-gray-3 mb-1 mt-2.5 h-1.5 w-10 rounded-full"
				horizontalAlignment="center"
			/>
			<slot />
			<StackLayout :height="safeBottom" />
		</StackLayout>
	</GridLayout>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { CoreTypes } from '@nativescript/core'

import { safeAreaBottom } from '@/utils/safeArea'

import type { EventData, View } from '@nativescript/core'

const props = defineProps<{ open: boolean }>()
defineEmits<{ close: [] }>()

const SHEET_OFFSET = 1000
const safeBottom = safeAreaBottom()
const visible = ref(false)

let sheetView: View | null = null
let scrimView: View | null = null

function onScrimLoaded(args: EventData) {
	scrimView = args.object as View
	scrimView.opacity = 0
}

function onSheetLoaded(args: EventData) {
	sheetView = args.object as View
	sheetView.translateY = SHEET_OFFSET
}

watch(
	() => props.open,
	(open) => (open ? openSheet() : closeSheet()),
)

function openSheet() {
	visible.value = true
	nextTick(() => {
		if (!sheetView || !scrimView) return
		sheetView.translateY = SHEET_OFFSET
		scrimView.opacity = 0
		sheetView.animate({
			translate: { x: 0, y: 0 },
			duration: 300,
			curve: CoreTypes.AnimationCurve.cubicBezier(0.22, 1, 0.36, 1),
		})
		scrimView.animate({ opacity: 0.4, duration: 260 })
	})
}

function closeSheet() {
	if (!sheetView || !scrimView) {
		visible.value = false
		return
	}
	Promise.all([
		sheetView.animate({
			translate: { x: 0, y: SHEET_OFFSET },
			duration: 260,
			curve: CoreTypes.AnimationCurve.cubicBezier(0.22, 1, 0.36, 1),
		}),
		scrimView.animate({ opacity: 0, duration: 220 }),
	])
		.catch(() => {})
		.finally(() => (visible.value = false))
}
</script>
