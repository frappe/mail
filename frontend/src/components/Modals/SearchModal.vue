<template>
	<Dialog v-model="show" :options="{ size: '2xl', position: 'top' }">
		<template #body>
			<div class="flex items-center px-4 py-2">
				<Search class="h-4 w-4" />
				<input
					v-model="query"
					icon-left="search"
					type="text"
					class="placeholder-ink-gray-4 w-full border-none bg-transparent text-base focus:ring-0"
					placeholder="Search"
				/>
			</div>
			<div v-if="results?.data?.length" class="px-2 pb-2">
				<div
					v-for="(result, idx) in results.data"
					:key="idx"
					class="hover:bg-surface-gray-3 flex rounded p-2 hover:cursor-pointer"
					@click="openMail(result.mailboxes[0].mailbox_id, result.thread_id)"
				>
					<div class="mr-2 space-y-1 truncate">
						<p class="truncate text-base font-semibold">
							{{ result.subject || __('[No subject]') }}
						</p>
						<p class="truncate text-sm">{{ getInterlocutors(result) }}</p>
					</div>
					<p class="text-ink-gray-4 ml-auto shrink-0 text-xs">
						{{ getFormattedDate(result.received_at) }}
					</p>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import { Search } from 'lucide-vue-next'
import { Dialog, createResource } from 'frappe-ui'

import { getFormattedDate } from '@/utils'

import type { Recipient } from '@/types'

const show = defineModel<boolean>()

const query = ref('')

const results = createResource({
	url: 'mail.api.mail.search_mails',
	makeParams: () => ({ query: query.value }),
})

watchDebounced(
	() => query.value,
	() => {
		if (query.value) results.reload()
		else results.reset()
	},
	{ debounce: 250 },
)

const router = useRouter()

const openMail = (mailbox: string, threadID: string) => {
	router.push({ name: 'Mail', params: { mailbox, threadID } })
	query.value = ''
	show.value = false
}

const getInterlocutors = (result: {
	from_name?: string
	from_email: string
	recipients?: Recipient[]
}) => {
	const sender = result.from_name || result.from_email
	if (!result.recipients?.length) return sender

	const seen = new Set<string>()
	const recipients = result.recipients
		.filter((r) => r.email !== result.from_email && !seen.has(r.email) && seen.add(r.email))
		.map((r) => r.display_name || r.email)
		.join(', ')

	return `${sender}, ${recipients}`
}
</script>
