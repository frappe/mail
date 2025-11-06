<template>
	<div class="flex space-x-2">
		<Button
			icon="search"
			:tooltip="__('Search ({0}+K)', [modifier])"
			variant="ghost"
			@click="showSearchModal = true"
		/>
		<Button
			icon-left="edit"
			:label="__('Compose')"
			:tooltip="__('Compose (C)')"
			@click="showSendModal = true"
		/>
	</div>

	<SendMail v-model="showSendModal" @reload-mails="emit('reloadMails')" />
	<SearchModal v-model="showSearchModal" />
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Button } from 'frappe-ui'

import { isMac } from '@/utils'
import SearchModal from '@/components/Modals/SearchModal.vue'
import SendMail from '@/components/SendMail.vue'

const emit = defineEmits(['reloadMails'])

const showSearchModal = ref(false)
const showSendModal = ref(false)

const modifier = computed(() => (isMac ? '⌘' : 'Ctrl'))

const handleKeydown = (e: KeyboardEvent) => {
	const target = e.target as HTMLElement
	if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
		return

	const key = e.key.toLowerCase()

	// Search shortcut
	if ((e.metaKey || e.ctrlKey) && key === 'k') {
		e.preventDefault()
		showSearchModal.value = true
		return
	}

	// Compose shortcut
	if (key === 'c' && !e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey) {
		e.preventDefault()
		showSendModal.value = true
	}
}

onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
</script>
