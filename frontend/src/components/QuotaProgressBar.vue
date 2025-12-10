<template>
	<div class="flex items-center gap-12">
		<!-- Circular Chart -->
		<div class="relative">
			<svg width="140" height="140" class="-rotate-90 transform">
				<!-- Background circle -->
				<circle
					cx="70"
					cy="70"
					:r="RADIUS"
					fill="none"
					:stroke="activeTheme === 'dark' ? '#2B2B2B' : '#F3F3F3'"
					stroke-width="8"
				/>
				<!-- Used storage arc -->
				<circle
					cx="70"
					cy="70"
					:r="RADIUS"
					fill="none"
					:stroke="activeTheme === 'dark' ? '#D4D4D4' : '#383838'"
					stroke-width="8"
					:stroke-dasharray="CIRCUMFERENCE"
					:stroke-dashoffset="animate ? usedOffset : CIRCUMFERENCE"
					stroke-linecap="round"
					style="transition: stroke-dashoffset 1s ease-out"
				/>
			</svg>

			<!-- Center text -->
			<div class="absolute inset-0 flex flex-col items-center justify-center space-y-1">
				<div class="text-xl font-semibold">
					{{ quota ? `${quota.toFixed(2)} GB` : __('Unlimited') }}
				</div>
				<div class="text-ink-gray-4 text-xs">{{ __('Total Quota') }}</div>
			</div>
		</div>

		<!-- Legend -->
		<div class="flex flex-col gap-4">
			<!-- Used Storage -->
			<div class="flex items-start gap-3">
				<span class="bg-surface-gray-6 mt-1 h-3 w-3 flex-shrink-0 rounded-sm" />
				<div class="space-y-1">
					<div class="text-sm font-medium">
						{{ usedQuota.toFixed(2) }} GB
						<span v-if="quota">({{ Math.round(usedPercentage) }}%)</span>
					</div>
					<div class="text-ink-gray-4 text-xs">{{ __('Used') }}</div>
				</div>
			</div>

			<!-- Available Storage -->
			<div v-if="quota" class="flex items-start gap-3">
				<span class="bg-surface-gray-2 mt-1 h-3 w-3 flex-shrink-0 rounded-sm" />
				<div class="space-y-1">
					<div class="text-sm font-medium">
						{{ availableQuota.toFixed(2) }} GB ({{ Math.round(availablePercentage) }}%)
					</div>
					<div class="text-ink-gray-4 text-xs">{{ __('Available') }}</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { useTheme } from '@/utils/composables'

const { quota, usedQuota } = defineProps<{ quota: number; usedQuota: number }>()

const { activeTheme } = useTheme()

const animate = ref(false)

const availableQuota = computed(() => quota - usedQuota)
const usedPercentage = computed(() => (quota ? (usedQuota / quota) * 100 : 0))
const availablePercentage = computed(() => (availableQuota.value / quota) * 100)
const usedOffset = computed(() => CIRCUMFERENCE - (usedPercentage.value / 100) * CIRCUMFERENCE)

onMounted(() => setTimeout(() => (animate.value = true), 100))

const RADIUS = 65
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
</script>
