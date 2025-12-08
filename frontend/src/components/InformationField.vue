<template>
	<div class="even:bg-surface-gray-1 flex items-center px-6 py-3.5 text-base last:rounded-b">
		<div class="text-ink-gray-5 w-1/4">{{ label }}</div>
		<div class="flex w-3/4 items-center truncate font-medium">{{ value }}</div>
	</div>
</template>

<script setup lang="ts">
defineProps<{ label: string; value: string }>()
</script>
