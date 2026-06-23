<template>
	<div class="animate-pulse sm:space-y-4 sm:px-5 sm:py-6">
		<div :class="{ 'px-3 py-5': isMobile }">
			<!-- Header: avatar, sender/recipients, date -->
			<div class="flex items-center space-x-3 pb-6">
				<div class="bg-surface-gray-3 h-8 w-8 shrink-0 rounded-full" />
				<div class="flex flex-1 justify-between">
					<div class="flex flex-col space-y-2">
						<div class="flex items-center space-x-2">
							<div class="bg-surface-gray-3 h-3.5 w-32 rounded" />
							<div class="bg-surface-gray-3 hidden h-3.5 w-48 rounded sm:block" />
						</div>
						<div class="bg-surface-gray-3 h-3 w-40 rounded" />
					</div>
					<div class="bg-surface-gray-3 h-3 w-16 shrink-0 self-start rounded" />
				</div>
			</div>

			<!-- Body: heading + paragraph lines -->
			<div class="space-y-2 py-4">
				<div class="bg-surface-gray-3 mb-6 h-5 w-3/5 rounded" />
				<div
					v-for="(width, i) in lineWidths"
					:key="i"
					class="bg-surface-gray-3 h-2 rounded"
					:style="{ width }"
				/>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { useScreenSize } from '@/utils/composables'

const { isMobile } = useScreenSize()

const lineWidths = ['90%', '75%', '82%', '60%', '88%', '45%']
</script>
