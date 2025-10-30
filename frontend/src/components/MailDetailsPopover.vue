<template>
	<Popover>
		<template #target="{ togglePopover }">
			<ChevronDown
				class="text-ink-gray-6 hover:bg-surface-gray-2 h-3.5 w-3.5 cursor-pointer rounded-sm"
				@click.stop="togglePopover()"
			/>
		</template>
		<template #body-main>
			<MailDetails :mail />
		</template>
	</Popover>
</template>

<script lang="ts" setup>
import { ChevronDown } from 'lucide-vue-next'
import { Popover } from 'frappe-ui'

import MailDetails from '@/components/MailDetails.vue'

import type { Mail } from '@/types'

defineProps<{ mail: Mail }>()
</script>
