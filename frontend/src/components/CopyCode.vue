<template>
	<div class="bg-surface-gray-1 flex justify-between rounded p-3">
		<pre class="text-wrap p-1 text-base">{{ code }}</pre>
		<Button
			icon="copy"
			size="sm"
			variant="ghost"
			class="shrink-0"
			:tooltip="__('Copy Code')"
			@click="copyToClipBoard"
		/>
	</div>
</template>

<script setup lang="ts">
import { Button } from 'frappe-ui'

import { raiseToast } from '@/utils'

const { code } = defineProps<{ code: string }>()

const copyToClipBoard = () =>
	navigator.clipboard
		.writeText(code)
		.then(() => raiseToast(__('Code copied to clipboard')))
		.catch(() => raiseToast(__('Failed to copy code'), 'error'))
</script>
