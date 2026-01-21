<template>
	<button
		class="flex items-center space-x-2 rounded-full border px-2 py-1.5"
		:class="{ 'hover:border-outline-gray-3 cursor-pointer': blobID }"
	>
		<Paperclip class="text-ink-gray-4 h-3.5 min-h-3.5 w-3.5 min-w-3.5" />
		<span class="truncate text-sm">{{ fileName }}</span>
	</button>
</template>

<script setup lang="ts">
import { Paperclip } from 'lucide-vue-next'

defineProps<{ fileName: string; blobID?: string }>()
</script>
