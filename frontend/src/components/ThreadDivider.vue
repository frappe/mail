<template>
	<div class="text-ink-gray-5 flex items-center px-1">
		<span class="flex-1 border-t" />
		<span class="rounded-full border px-2 py-1 text-xs"> {{ message }} </span>
		<span class="flex-1 border-t" />
	</div>
</template>

<script setup lang="ts">
defineProps<{ message: string }>()
</script>
