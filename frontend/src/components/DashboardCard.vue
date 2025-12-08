<template>
	<div class="flex shrink-0 flex-col rounded-md border">
		<div class="h-13 py-auto flex shrink-0 items-center justify-between border-b px-4">
			<h2>{{ title }}</h2>
			<slot name="actions">
				<Button variant="ghost" :label="buttonLabel" @click="emit('action')" />
			</slot>
		</div>
		<slot />
	</div>
</template>

<script setup lang="ts">
import { Button } from 'frappe-ui'

const { buttonLabel = __('Add') } = defineProps<{ title: string; buttonLabel?: string }>()

const emit = defineEmits(['action'])
</script>
