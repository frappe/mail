<template>
	<GridLayout columns="auto, *" class="px-5 py-3" @tap="$emit('tap')">
		<Label
			col="0"
			:text="lucide(icon)"
			class="font-lucide mr-3.5 text-xl"
			:class="danger ? 'text-ink-red-3' : 'text-ink-gray-7'"
			verticalAlignment="center"
		/>
		<StackLayout col="1" verticalAlignment="center">
			<Label
				:text="label"
				class="text-base font-semibold"
				:class="danger ? 'text-ink-red-3' : 'text-ink-gray-9'"
			/>
			<Label v-if="sub" :text="sub" class="text-ink-gray-5 mt-0.5 text-sm" />
		</StackLayout>
	</GridLayout>
</template>

<script setup lang="ts">
import { lucide } from '@/utils/lucide'

defineProps<{ icon: string; label: string; sub?: string; danger?: boolean }>()
defineEmits<{ tap: [] }>()
</script>
