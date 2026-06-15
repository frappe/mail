<template>
	<StackLayout class="border-outline-gray-1 border-b">
		<!-- chips wrap in col 0; the trailing slot (Cc/Bcc toggle) is pinned to the
		     top-right in col 1 so it stays put as chips wrap to new rows -->
		<GridLayout columns="*, auto">
			<!-- label + chips + input, wrapping like the web RecipientField. The tap
			     to expand lives here (col 0), not on the row, so the col-1 chevron
			     toggles Cc/Bcc without also focusing this field. -->
			<FlexboxLayout
				col="0"
				flexWrap="wrap"
				alignItems="center"
				class="py-1.5 pl-4"
				@tap="expand"
			>
				<Label
					:text="label"
					class="text-ink-gray-5 my-1 w-12 text-base"
					verticalAlignment="center"
				/>

				<GridLayout
					v-for="chip in visibleChips"
					:key="chip.email"
					columns="auto, auto"
					class="bg-surface-gray-3 my-1 mr-1.5 rounded-full py-1.5 pl-3 pr-2"
				>
					<Label
						col="0"
						:text="chip.display_name || chip.email"
						class="text-ink-gray-9 text-sm font-medium"
						verticalAlignment="center"
					/>
					<Label
						col="1"
						:text="lucide('x')"
						class="font-lucide text-ink-gray-4 ml-1 text-sm"
						verticalAlignment="center"
						@tap="remove(chip)"
					/>
				</GridLayout>

				<!-- collapsed overflow: tap to expand the field and reveal the rest -->
				<GridLayout
					v-if="hiddenCount"
					columns="auto"
					class="bg-surface-gray-3 my-1 mr-1.5 rounded-full px-3 py-1.5"
					horizontalAlignment="left"
					@tap="expand"
				>
					<Label
						:text="`+${hiddenCount}`"
						class="text-ink-gray-7 text-sm font-medium"
						verticalAlignment="center"
					/>
				</GridLayout>

				<TextField
					v-show="!collapsed"
					v-model="text"
					flexGrow="1"
					class="text-ink-gray-9 my-1"
					width="120"
					height="34"
					:hint="modelValue.length ? '' : hint"
					autocapitalizationType="none"
					autocorrect="false"
					keyboardType="email"
					returnKeyType="done"
					@loaded="onFieldLoaded"
					@textChange="onTextChange"
					@returnPress="onReturn"
					@blur="onBlur"
					@focus="onFocus"
				/>
			</FlexboxLayout>

			<!-- Pinned to the first row's vertical center (top + pt-3 ≈ the single
			     line's middle), so it sits with "To" and stays there as chips wrap. -->
			<StackLayout col="1" verticalAlignment="top" class="pr-4 pt-3.5">
				<slot name="trailing" />
			</StackLayout>
		</GridLayout>

		<!-- contact suggestions -->
		<StackLayout v-if="suggestions.length" class="pb-1.5">
			<GridLayout
				v-for="s in suggestions"
				:key="s"
				class="py-2 pl-20 pr-4"
				@tap="chooseSuggestion(s)"
			>
				<Label :text="s" class="text-ink-gray-8 text-sm" verticalAlignment="center" />
			</GridLayout>
		</StackLayout>
	</StackLayout>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { isAndroid } from '@nativescript/core'

import { useApi } from '@/utils/api'
import { lucide } from '@/utils/lucide'
import { flattenField } from '@/utils/nativeField'

import type { DraftRecipient } from '@mail/types'
import type { EventData, PropertyChangeData, View } from '@nativescript/core'

const props = defineProps<{
	label: string
	modelValue: DraftRecipient[]
	account: string
	hint?: string
}>()
const emit = defineEmits<{
	'update:modelValue': [value: DraftRecipient[]]
	pending: [text: string]
	focus: []
}>()

const api = useApi()
const text = ref('')
const suggestions = ref<string[]>([])
let suggestTimer: ReturnType<typeof setTimeout> | null = null

// Collapse long recipient lists when the field isn't focused: overflow chips are
// hidden behind a "+N" pill (each long address ~one row, so 2 chips ≈ 2 rows).
// Tapping the field (or the pill) focuses it and reveals everything.
const COLLAPSE_AT = 2
const focused = ref(false)
const collapsed = computed(() => !focused.value && props.modelValue.length > COLLAPSE_AT)
const visibleChips = computed(() =>
	collapsed.value ? props.modelValue.slice(0, COLLAPSE_AT) : props.modelValue,
)
const hiddenCount = computed(() => (collapsed.value ? props.modelValue.length - COLLAPSE_AT : 0))

function setChips(next: DraftRecipient[]) {
	emit('update:modelValue', next)
}

function remove(chip: DraftRecipient) {
	setChips(props.modelValue.filter((c) => c.email !== chip.email))
}

// RFC-lite: local@domain.tld with no spaces.
function isValidEmail(s: string): boolean {
	return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s.trim())
}

function clearInput() {
	text.value = ''
	suggestions.value = []
	emit('pending', '')
}

// Adds a chip only for a valid, non-duplicate address. Returns whether it added.
function addEmail(email: string): boolean {
	const clean = email.trim().replace(/,+$/, '')
	if (!isValidEmail(clean)) return false
	if (!props.modelValue.some((c) => c.email === clean)) {
		setChips([...props.modelValue, { email: clean }])
	}
	return true
}

function chooseSuggestion(email: string) {
	addEmail(email)
	clearInput()
}

// Commit the typed text into a chip (Enter / blur / delimiter). Invalid input is
// left in the field so the user can correct it rather than silently dropping it.
function commit() {
	if (text.value.trim() && addEmail(text.value)) clearInput()
}

let fieldView: View | null = null
function onFieldLoaded(args: EventData) {
	fieldView = args.object as View
	flattenField(args)
	// Android's EditText top-aligns single-line text once its background is
	// dropped; with our fixed input height that leaves the text sitting high.
	// Zero the vertical padding and center the text within the height.
	if (isAndroid) {
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		const et = (args.object as any).android
		et?.setPadding?.(et.getPaddingLeft(), 0, et.getPaddingRight(), 0)
		et?.setGravity?.(0x10 | 0x03) // Gravity.CENTER_VERTICAL | Gravity.LEFT
	}
}

// Enter/Return commits the address but keeps focus in the field so the user can
// type another recipient instead of advancing to the next field.
function onReturn() {
	commit()
	setTimeout(() => fieldView?.focus(), 0)
}

function onFocus() {
	focused.value = true
	emit('focus')
}

function onBlur() {
	focused.value = false
	commit()
}

// Tapping the field/"+N" pill expands it. The input is hidden (v-show) while
// collapsed and a hidden view can't take focus, so reveal it first (focused →
// collapsed = false), then focus on the next tick once it's visible.
function expand() {
	if (focused.value) {
		fieldView?.focus()
		return
	}
	focused.value = true
	nextTick(() => fieldView?.focus())
}

// Let parents focus this field (e.g. ComposeView focusing To when forwarding).
defineExpose({ focus: expand })

function onTextChange(args: PropertyChangeData) {
	const value = (args.value ?? '') as string
	// Commit on comma/space/newline; valid tokens become chips, anything invalid
	// stays in the field (so a typo isn't silently dropped) along with the fragment.
	if (/[,\s]/.test(value)) {
		const parts = value.split(/[,\s]+/)
		const remainder = parts.pop() ?? ''
		const rejected = parts.filter(Boolean).filter((p) => !addEmail(p))
		suggestions.value = []
		const next = [...rejected, remainder].filter(Boolean).join(' ')
		text.value = next
		emit('pending', next)
		return
	}
	emit('pending', value)
	queueSuggestions(value)
}

function queueSuggestions(query: string) {
	if (suggestTimer) clearTimeout(suggestTimer)
	const q = query.trim()
	if (q.length < 2) {
		suggestions.value = []
		return
	}
	suggestTimer = setTimeout(async () => {
		try {
			const res = await api.call<string[]>('mail.api.mail.get_email_suggestions', {
				account: props.account,
				query: q,
				limit: 3,
			})
			suggestions.value = (res || []).filter(
				(e) => !props.modelValue.some((c) => c.email === e),
			)
		} catch {
			suggestions.value = []
		}
	}, 250)
}

// Clearing the field externally (e.g. on reset) should drop suggestions too.
watch(text, (v) => {
	if (!v) suggestions.value = []
})
</script>
