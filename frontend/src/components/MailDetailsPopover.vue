<template>
	<Popover>
		<template #target="{ togglePopover }">
			<ChevronDown
				class="text-ink-gray-6 hover:bg-surface-gray-2 h-3 w-3 cursor-pointer rounded-sm"
				@click.stop="togglePopover()"
			/>
		</template>
		<template #body-main>
			<div class="grid max-h-96 max-w-md grid-cols-5 gap-2 overflow-y-auto p-3 text-sm">
				<span class="text-ink-gray-5 col-span-1">{{ __('From:') }}</span>
				<span class="col-span-4">
					<span class="font-semibold">
						{{ mail.from_name || mail.from_email }}
					</span>
					<span v-if="mail.from_name">
						{{ ` <${mail.from_email}>` }}
					</span>
				</span>
				<template v-for="field in FIELDS" :key="field.label">
					<span class="text-ink-gray-4 col-span-1">{{ field.label }}</span>
					<span class="col-span-4">{{ field.value() }} </span>
				</template>
			</div>
		</template>
	</Popover>
</template>

<script lang="ts" setup>
import { computed, inject } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import { Popover } from 'frappe-ui'

import { getGroupedRecipients } from '@/utils'

import type { Mail } from '@/types'

const dayjs = inject('$dayjs')

const { mail } = defineProps<{ mail: Mail }>()

const recipients = computed(() => getGroupedRecipients(mail.recipients, true, true))

const FIELDS = [
	{
		condition: mail.reply_to.length > 0,
		label: __('Reply To: '),
		value: () => mail.reply_to.map((rt) => rt.email).join(', '),
	},
	{
		label: __('To: '),
		value: () => recipients.value.to,
	},
	{
		condition: !!recipients.value.cc,
		label: __('Cc: '),
		value: () => recipients.value.cc,
	},
	{
		condition: !!recipients.value.bcc,
		label: __('Bcc: '),
		value: () => recipients.value.bcc,
	},
	{
		label: __('Date: '),
		value: () => dayjs(mail.received_at).format('MMM D, YYYY, h:mm A'),
	},
	{
		condition: !!mail.subject,
		label: __('Subject: '),
		value: () => mail.subject,
	},
].filter((field) => field.condition !== false)
</script>
