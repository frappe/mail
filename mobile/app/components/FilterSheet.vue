<template>
	<!-- Bottom sheet: scrim + a sheet that slides up. Mirrors AccountSheet. -->
	<GridLayout :visibility="visible ? 'visible' : 'collapse'" rows="*, auto">
		<StackLayout
			rowSpan="2"
			class="bg-surface-gray-7"
			@loaded="onScrimLoaded"
			@tap="$emit('close')"
		/>

		<StackLayout
			row="1"
			class="bg-surface-white rounded-t-3xl pb-8"
			@loaded="onSheetLoaded"
			@tap="() => {}"
		>
			<StackLayout
				class="bg-surface-gray-3 mb-1 mt-2.5 h-1.5 w-10 rounded-full"
				horizontalAlignment="center"
			/>
			<Label
				:text="__('Filter')"
				class="text-ink-gray-4 px-5 pb-1 pt-3 text-xs font-semibold uppercase"
			/>
			<GridLayout
				v-for="o in options"
				:key="String(o.value)"
				columns="*, auto"
				class="px-5 py-2.5"
				@tap="onSelect(o.value)"
			>
				<Label
					col="0"
					:text="o.label"
					class="text-base"
					:class="
						o.value === current ? 'text-ink-gray-9 font-semibold' : 'text-ink-gray-8'
					"
					verticalAlignment="center"
				/>
				<Label
					v-if="o.value === current"
					col="1"
					:text="lucide('check')"
					class="font-lucide text-ink-gray-9 text-lg"
					verticalAlignment="center"
				/>
			</GridLayout>
			<StackLayout :height="safeBottom" />
		</StackLayout>
	</GridLayout>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { CoreTypes } from '@nativescript/core'

import { lucide } from '@/utils/lucide'
import { safeAreaBottom } from '@/utils/safeArea'

import type { ThreadFilter } from '@/types/navigation'
import type { EventData, View } from '@nativescript/core'

const props = defineProps<{ open: boolean; current: ThreadFilter; showStarred: boolean }>()
const emit = defineEmits<{ close: []; select: [value: ThreadFilter] }>()

const SHEET_OFFSET = 1000 // enough to push the sheet fully below the screen
const safeBottom = safeAreaBottom()
const visible = ref(false)

let sheetView: View | null = null
let scrimView: View | null = null

// Mirrors the web FILTER_OPTIONS; Starred is hidden in Trash / the Starred view.
const options = computed<{ label: string; value: ThreadFilter }[]>(() => [
	{ label: __('All Mails'), value: null },
	{ label: __('Unread'), value: 'unread' },
	...(props.showStarred ? [{ label: __('Starred'), value: 'starred' as ThreadFilter }] : []),
	{ label: __('Has attachments'), value: 'has_attachments' },
])

function onSelect(value: ThreadFilter) {
	emit('select', value)
	emit('close')
}

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
