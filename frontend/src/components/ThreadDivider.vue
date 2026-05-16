<template>
	<div class="text-ink-gray-5 flex items-center">
		<span class="flex-1 border-t" />
		<span class="rounded-full border px-2 py-1 text-sm"> {{ message }} </span>
		<span class="flex-1 border-t" />
	</div>
</template>

<script setup lang="ts">
defineProps<{ message: string }>()
</script>
