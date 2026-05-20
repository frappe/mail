<template>
	<div
		ref="container"
		class="flex w-full flex-1 cursor-text flex-wrap items-center gap-2 rounded transition-colors"
		:class="{ 'ring-outline-gray-3 ring-2': isDragOver && !isDragging }"
		@keydown.capture="handleContainerKeydown"
		@dragover.prevent="isDragOver = true"
		@dragleave="isDragOver = false"
		@drop.prevent="handleDrop"
		@click="handleClick"
	>
		<button
			v-for="(v, i) in displayedRecipients"
			ref="tags"
			:key="v.email"
			class="bg-surface-gray-2 flex min-h-7 items-center space-x-1.5 rounded px-2 text-base focus:outline-none"
			:class="{
				'ring-outline-gray-3 ring-2': focusedTagIndex === i,
			}"
			:draggable="true"
			@click.stop="focusedTagIndex = i"
			@focus="focusedTagIndex = i"
			@blur="focusedTagIndex = -1"
			@keydown.delete.stop="removeValueAt(i)"
			@dragstart="handleDragStart($event, v)"
			@dragend="handleDragEnd($event, v)"
		>
			<Avatar :image="v.image" :label="v.display_name || v.email" size="xs" />
			<span :class="{ 'max-w-32 truncate': isMobile && !isFocused }">
				{{ v.display_name || v.email }}
			</span>
			<X v-if="!isMobile || isFocused" class="icon" @click.stop="removeValue(v.email)" />
		</button>
		<span
			v-if="isMobile && !isFocused && selectedRecipients.length > 2"
			class="text-ink-gray-6"
		>
			{{ `+${selectedRecipients.length - 2}` }}
		</span>
		<Combobox
			v-model="input"
			placeholder=""
			:options
			:open-on-click="false"
			:allow-custom-value="true"
			class="border-none !bg-inherit !ring-0 sm:w-80"
			@input="handleInput"
			@keydown.delete.capture.stop="handleDelete($event.target.value)"
			@paste="handlePaste"
			@focusin="isSearchFocused = true"
			@focusout="isSearchFocused = false"
		>
			<template #suffix> <span /> </template>
			<template #item-prefix="{ item }">
				<Avatar :image="item.image" :label="item.display_name || item.email" />
			</template>
			<template #item-label="{ item }">
				<div class="truncate">{{ item.display_name || item.email }}</div>
				<div class="text-p-sm text-ink-gray-5 truncate">{{ item.email }}</div>
			</template>
		</Combobox>
	</div>
</template>

<script lang="ts">
let droppedOnTarget = false
</script>

<script setup lang="ts">
import { computed, nextTick, ref, useTemplateRef, watch } from 'vue'
import { onClickOutside, useDebounceFn } from '@vueuse/core'
import { X } from 'lucide-vue-next'
import { Avatar, Combobox, createResource } from 'frappe-ui'

import { type DraftRecipient } from '@/types'
import { isEmail } from '@/utils'
import { useScreenSize } from '@/utils/composables'
import { userStore } from '@/stores/user'

const emit = defineEmits(['showCcBcc'])

const selectedRecipients = defineModel<DraftRecipient[]>({ default: () => [] })

const displayedRecipients = computed(() => {
	if (!selectedRecipients.value?.length) return []
	if (selectedRecipients.value.length <= 2 || !isMobile.value || isFocused.value)
		return selectedRecipients.value

	return selectedRecipients.value.slice(0, 2)
})

const { isMobile } = useScreenSize()
const store = userStore()

const containerRef = useTemplateRef('container')
const tagsRef = useTemplateRef('tags')

const input = ref('')
const focusedTagIndex = ref(-1)
const isClicked = ref(false)
const isSearchFocused = ref(false)

const isFocused = computed(() => isClicked.value || isSearchFocused.value)

onClickOutside(containerRef, () => (isClicked.value = false))

const selectedEmails = computed(() => selectedRecipients.value.map((v) => v.email))

const handleInput = useDebounceFn((text: string) => {
	if (text) mailContacts.reload(text)
}, 200)

const handleDelete = (currentValue: string) => {
	if (!currentValue && selectedRecipients.value.length) tagsRef.value?.at(-1)?.focus()
}

const handlePaste = (e: ClipboardEvent) => {
	e.preventDefault()
	const pastedText = e.clipboardData?.getData('text') || ''
	if (pastedText) addValues(pastedText)
	input.value = ''
}

const setFocus = () => containerRef.value?.querySelector('input')?.focus()
const handleClick = () => {
	isClicked.value = true
	nextTick(setFocus)
}
defineExpose({ setFocus })

const handleContainerKeydown = (e: KeyboardEvent) => {
	const inputEl = containerRef.value?.querySelector('input') as HTMLInputElement | null
	const isInputFocused = document.activeElement === inputEl
	const isAtInputStart = inputEl?.selectionStart === 0 && inputEl?.selectionEnd === 0

	if (e.key === 'ArrowLeft') {
		if (isInputFocused && isAtInputStart && selectedRecipients.value.length) {
			e.preventDefault()
			tagsRef.value?.at(-1)?.focus()
		} else if (focusedTagIndex.value > 0) {
			e.preventDefault()
			tagsRef.value?.[focusedTagIndex.value - 1]?.focus()
		}
	}

	if (e.key === 'ArrowRight' && focusedTagIndex.value >= 0) {
		e.preventDefault()
		const nextIndex = focusedTagIndex.value + 1
		const target = tagsRef.value?.[nextIndex] ?? inputEl
		target?.focus()
	}
}

const removeValueAt = (i: number) => {
	selectedRecipients.value.splice(i, 1)
	nextTick(() => {
		if (!tagsRef.value?.length) setFocus()
		else tagsRef.value[Math.min(i, tagsRef.value.length - 1)]?.focus()
	})
}

watch(input, (val) => addValues(val))

const addValues = (values: string) => {
	if (!values) return

	values
		.split(/[\n,]+/)
		.map((v) => v.trim())
		.filter((v) => isEmail(v) && !selectedEmails.value.includes(v))
		.forEach(addValue)

	input.value = ''
}

const addValue = (value: string) => {
	const contact = mailContacts.data?.find((c) => c.email === value)
	if (contact) selectedRecipients.value.push(contact)
	else selectedRecipients.value.push({ email: value })
}

const removeValue = (value: string) =>
	(selectedRecipients.value = selectedRecipients.value.filter((v) => v.email !== value))

const isDragging = ref(false)
const isDragOver = ref(false)

const handleDragStart = (e: DragEvent, recipient: DraftRecipient) => {
	emit('showCcBcc')
	droppedOnTarget = false
	isDragging.value = true
	e.dataTransfer?.setData('recipient', JSON.stringify(recipient))
}

const handleDragEnd = (_: DragEvent, recipient: DraftRecipient) => {
	if (droppedOnTarget) removeValue(recipient.email)
	isDragging.value = false
	isDragOver.value = false
}

const handleDrop = (e: DragEvent) => {
	isDragOver.value = false
	const data = e.dataTransfer?.getData('recipient')
	if (!data) return
	const recipient: DraftRecipient = JSON.parse(data)
	if (selectedEmails.value.includes(recipient.email)) return

	selectedRecipients.value.push(recipient)
	droppedOnTarget = true
}

const mailContacts = createResource({
	url: 'mail.api.contacts.get_contacts',
	auto: false,
	makeParams: (text: string) => ({
		account: store.account,
		filter: { operator: 'OR', conditions: [{ text }, { email: text }] },
	}),
	transform: (data) =>
		data.map((option) => ({
			label: option.full_name || option.email,
			value: option.email,
			email: option.email,
			display_name: option.full_name,
			image: option.user_image,
		})),
})

const options = computed(
	() =>
		mailContacts.data?.filter((option) => !selectedEmails.value.includes(option.email)) || [],
)
</script>
