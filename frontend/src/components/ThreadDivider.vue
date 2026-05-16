<template>
	<div class="text-ink-gray-5 flex items-center">
		<span class="flex-1 border-t" />
		<span class="rounded-full border px-3.5 py-2 text-sm sm:px-2 sm:py-1">
			{{ message }}
		</span>
		<span class="flex-1 border-t" />
	</div>
</template>

<script setup lang="ts">
defineProps<{ message: string }>()
</script>
