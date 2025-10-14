<template>
	<Dialog v-model="show" :options="{ size: '2xl', position: 'top' }">
		<template #body>
			<div class="flex items-center px-4 py-2">
				<Search class="text-ink-gray-5 h-4 w-4" />
				<input
					v-model="filter.text"
					icon-left="search"
					type="text"
					class="placeholder-ink-gray-4 w-full border-none bg-transparent text-base focus:ring-0"
					placeholder="Search"
					@keyup.enter="openSearchPage"
				/>
				<Button variant="ghost" @click="showAdvancedFilters = !showAdvancedFilters">
					<template #icon>
						<SlidersHorizontal class="text-ink-gray-5 h-4 w-4" />
					</template>
				</Button>
			</div>
			<template v-if="showAdvancedFilters">
				<div class="space-y-4 border-t p-4">
					<FormControl
						v-model="filter.inMailbox"
						type="select"
						:label="__('Folder')"
						:options="mailboxOptions"
					/>
					<FormControl v-model="filter.subject" :label="__('Subject')" />
					<FormControl v-model="filter.from" :label="__('From')" />
					<FormControl v-model="filter.to" :label="__('To')" />
					<FormControl v-model="filter.cc" :label="__('Cc')" />
					<FormControl v-model="filter.bcc" :label="__('Bcc')" />
					<div class="flex space-x-4">
						<FormControl
							v-model="filter.after"
							type="date"
							:label="__('From Date')"
							class="w-full"
						/>
						<FormControl
							v-model="filter.before"
							type="date"
							:label="__('To Date')"
							class="w-full"
						/>
					</div>
				</div>
				<div class="flex w-full justify-end space-x-4 border-t p-4">
					<Button
						:label="__('Clear Filters')"
						class="w-32"
						@click="Object.assign(filter, DEFAULT_FILTER)"
					/>
					<Button
						:label="__('Search')"
						variant="solid"
						class="w-32"
						@click="openSearchPage"
					/>
				</div>
			</template>
			<div v-else-if="results?.data?.length" class="px-2 pb-2">
				<div
					v-for="(result, idx) in results.data[0]"
					:key="idx"
					class="hover:bg-surface-gray-3 flex rounded p-2 hover:cursor-pointer"
					@click="openThread(result.mailboxes[0].mailbox_id, result.thread_id)"
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
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import { Search, SlidersHorizontal } from 'lucide-vue-next'
import { Button, Dialog, FormControl, createResource } from 'frappe-ui'

import { getFormattedDate } from '@/utils'
import { userStore } from '@/stores/user'

import type { Recipient } from '@/types'

const show = defineModel<boolean>()

const { mailboxes } = userStore()

const DEFAULT_FILTER = {
	text: '',
	inMailbox: '',
	subject: '',
	from: '',
	to: '',
	cc: '',
	bcc: '',
	after: '',
	before: '',
}
const filter = reactive({ ...DEFAULT_FILTER })
const filteredFilter = computed(() =>
	Object.fromEntries(Object.entries(filter).filter(([, v]) => Boolean(v))),
)
const showAdvancedFilters = ref(false)

const mailboxOptions = computed(() =>
	[{ label: __('All folders'), value: '' }].concat(
		mailboxes.data.map((m: { id: string; _name: string }) => ({
			label: m._name,
			value: m.id,
		})),
	),
)

const results = createResource({
	url: 'mail.api.mail.search_mails',
	makeParams: () => ({ filter: filteredFilter.value }),
})

watchDebounced(
	() => filter.text,
	(val) => {
		if (val) results.reload()
		else results.reset()
	},
	{ debounce: 250 },
)

const openSearchPage = () => {
	router.push({ name: 'Mailbox', params: { mailbox: 'search' }, query: filteredFilter.value })
	show.value = false
}

const router = useRouter()

const openThread = (mailbox: string, threadID: string) => {
	router.push({ name: 'Mail', params: { mailbox, threadID } })
	Object.assign(filter, DEFAULT_FILTER)
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
