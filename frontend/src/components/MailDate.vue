<template>
	<Tooltip :text="tooltipText" :disabled="inList">
		<div class="text-ink-gray-5 text-nowrap text-xs" :class="{ 'mr-1': !inList }">
			{{ formattedDate }}
		</div>
	</Tooltip>
</template>
<script setup lang="ts">
import { computed, inject } from 'vue'
import { useTimeAgo } from '@vueuse/core'
import { Tooltip } from 'frappe-ui'

const { datetime, inList = false } = defineProps<{ datetime: string; inList?: boolean }>()

const dayjs = inject('$dayjs')

const formattedDate = computed(() => {
	if (!inList) {
		const timeAgo = useTimeAgo(datetime).value
		return __(timeAgo.charAt(0).toUpperCase() + timeAgo.slice(1))
	}
	if (dayjs(datetime).isToday()) return dayjs(datetime).format('h:mm A')
	if (dayjs(datetime).isYesterday()) return __('Yesterday')
	if (dayjs(datetime).year() === dayjs().year()) return dayjs(datetime).format('D MMM')
	return dayjs(datetime).format('D MMM YYYY')
})

const tooltipText = computed(() =>
	__(`${dayjs(datetime).format('D MMM YYYY')} at ${dayjs(datetime).format('h:mm A')}`),
)
</script>
