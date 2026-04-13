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
					:stroke="activeTheme === 'Dark Mode' ? '#2B2B2B' : '#F3F3F3'"
					stroke-width="8"
				/>
				<!-- Used storage arc -->
				<circle
					cx="70"
					cy="70"
					:r="RADIUS"
					fill="none"
					:stroke="activeTheme === 'Dark Mode' ? '#D4D4D4' : '#383838'"
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
						<span v-if="quota">({{ usedPercentage.toFixed(1) }}%)</span>
					</div>
					<div class="text-ink-gray-4 text-xs">{{ __('Used') }}</div>
				</div>
			</div>

			<!-- Available Storage -->
			<div v-if="quota" class="flex items-start gap-3">
				<span class="bg-surface-gray-2 mt-1 h-3 w-3 flex-shrink-0 rounded-sm" />
				<div class="space-y-1">
					<div class="text-sm font-medium">
						{{ availableQuota.toFixed(2) }} GB ({{ availablePercentage.toFixed(1) }}%)
					</div>
					<div class="text-ink-gray-4 text-xs">{{ __('Available') }}</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'

import { getSystemTheme } from '@/utils'

const { quota, usedQuota } = defineProps<{ quota: number; usedQuota: number }>()

const user = inject('$user')

const activeTheme = computed(() =>
	user.data.color_scheme === 'System Default' ? getSystemTheme() : user.data.color_scheme,
)

const animate = ref(false)

const availableQuota = computed(() => quota - usedQuota)
const usedPercentage = computed(() => (quota ? (usedQuota / quota) * 100 : 0))
const availablePercentage = computed(() => (availableQuota.value / quota) * 100)
const usedOffset = computed(() => CIRCUMFERENCE - (usedPercentage.value / 100) * CIRCUMFERENCE)

onMounted(() => setTimeout(() => (animate.value = true), 100))

const RADIUS = 65
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
</script>
