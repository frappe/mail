<template>
	<div class="flex space-x-2">
		<Button icon="search" variant="ghost" @click="showSearchModal = true" />
		<Button icon-left="edit" :label="__('Compose')" @click="showSendModal = true" />
	</div>

	<SendMail v-model="showSendModal" />
	<SearchModal v-model="showSearchModal" />
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Button } from 'frappe-ui'

import SearchModal from '@/components/Modals/SearchModal.vue'
import SendMail from '@/components/SendMail.vue'

const showSearchModal = ref(false)
const showSendModal = ref(false)

const handleKeydown = (event: KeyboardEvent) => {
	if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
		event.preventDefault()
		showSearchModal.value = true
	}
}

onMounted(() => document.addEventListener('keydown', handleKeydown))
onUnmounted(() => document.removeEventListener('keydown', handleKeydown))
</script>
