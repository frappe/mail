<template>
	<div class="bg-surface-white fixed inset-0 z-10" :class="{ hidden: !show }">
		<slot name="body" />
	</div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'

const show = defineModel<boolean>()

const close = () => {
	if (show.value) show.value = false
}

watch(show, (val) => {
	if (val) history.pushState(null, '')
})

onMounted(() => window.addEventListener('popstate', close))
onUnmounted(() => window.removeEventListener('popstate', close))
</script>
