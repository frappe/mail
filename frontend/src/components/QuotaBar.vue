<template>
	<div class="flex flex-col space-y-2 rounded p-2">
		<div class="flex w-full">
			<div class="flex items-center space-x-2">
				<Cloud class="stroke-1.5 h-4 w-4" />
				<span v-if="!isCollapsed" class="text-sm"> {{ __('Storage') }} </span>
			</div>
		</div>
		<div class="bg-surface-gray-4 h-1 w-auto rounded-full">
			<div
				class="h-1 rounded-full"
				:class="
					quota.data?.used_percentage > 80 ? 'bg-surface-red-6' : 'bg-surface-gray-7'
				"
				:style="{ width: `${quota.data?.used_percentage || 0}%`, maxWidth: '100%' }"
			/>
		</div>
		<span class="text-ink-gray-5 line-clamp-1 text-xs" :class="{ invisible: isCollapsed }">
			{{ displayedQuota }}
		</span>
	</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Cloud } from 'lucide-vue-next'
import { createResource } from 'frappe-ui'

import { formatBytes } from '@/utils'
import { userStore } from '@/stores/user'

const { isCollapsed } = defineProps<{ isCollapsed: boolean }>()

const { account } = userStore()

const quota = createResource({
	url: 'mail.api.account.get_quota',
	auto: true,
	makeParams: () => ({ account }),
	cache: ['quota', account],
})

const displayedQuota = computed(() => {
	if (!quota.data) return ''

	if (quota.data.disk_quota <= 0)
		return __('Unlimited ({0} used)', [formatBytes(quota.data.used_quota)])

	return __('{0}% of {1} used', [
		quota.data.used_percentage.toFixed(2),
		formatBytes(quota.data.disk_quota),
	])
})
</script>
