<template>
	<div class="even:bg-surface-gray-1 flex items-center px-5 py-3.5 text-base last:rounded-b">
		<div class="text-ink-gray-5 w-1/3">{{ label }}</div>
		<div class="flex w-2/3 items-center font-medium">
			<span class="truncate">{{ value }}</span>
		</div>
	</div>
</template>

<script setup lang="ts">
defineProps<{ label: string; value: string }>()
</script>
