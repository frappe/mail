<template>
	<div class="flex h-screen items-center justify-center">
		<p class="text-ink-gray-5 text-base">{{ __('Redirecting...') }}</p>
	</div>
</template>
<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
onMounted(() => router.replace('/'))
</script>
