<template>
	<component
		:is="isMobile ? SearchMobileLayout : Dialog"
		v-model="show"
		:options="{ size: '2xl', paddingTop: '2%' }"
	>
		<template #body>
			<div class="bg-surface-white">
				<div
					class="flex items-center px-4 py-2"
					:class="{ 'border-b': showAdvancedFilters || results?.data?.length }"
				>
					<Button v-if="isMobile" variant="ghost" @click="show = false">
						<template #icon>
							<ChevronLeft class="text-ink-gray-5 h-4 w-4" />
						</template>
					</Button>
					<Search v-else class="text-ink-gray-5 h-4 w-4" />
					<input
						ref="searchInput"
						v-model="filter.text"
						icon-left="search"
						type="search"
						class="placeholder-ink-gray-4 w-full border-none bg-transparent text-base focus:ring-0"
						placeholder="Search"
						@click="showAdvancedFilters = false"
						@keyup.enter="openSearchPage"
					/>
					<div class="group">
						<span
							v-if="advancedFiltersLength"
							class="bg-surface-gray-7 text-ink-gray-1 border-outline-white absolute right-4 top-3 flex h-3 w-3 items-center justify-center rounded-full border text-[6px] font-bold group-hover:invisible"
						>
							{{ advancedFiltersLength }}
						</span>
						<Button
							variant="ghost"
							@click="showAdvancedFilters = !showAdvancedFilters"
						>
							<template #icon>
								<SlidersHorizontal class="text-ink-gray-5 h-4 w-4" />
							</template>
						</Button>
					</div>
				</div>
				<template v-if="showAdvancedFilters">
					<div class="space-y-4 p-4">
						<FormControl
							v-model="filter.inMailbox"
							type="select"
							:label="__('Look In')"
							:options="mailboxOptions"
						/>
						<FormControl v-model="filter.subject" :label="__('Subject')" />
						<FormControl v-model="filter.from" :label="__('From')" />
						<FormControl v-model="filter.to" :label="__('To')" />
						<div class="flex space-x-4">
							<FormControl v-model="filter.cc" :label="__('Cc')" class="w-full" />
							<FormControl v-model="filter.bcc" :label="__('Bcc')" class="w-full" />
						</div>
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
						<FormControl
							v-model="filter.hasAttachment"
							type="select"
							:label="__('Attachments')"
							:options="getAttachmentOptions()"
						/>
						<FormControl
							v-model="filter.isRead"
							type="select"
							:label="__('Read Status')"
							:options="getReadStatusOptions()"
						/>
					</div>
					<div
						class="flex w-full p-4"
						:class="isMobile ? 'flex-col space-y-4' : 'justify-end space-x-4'"
					>
						<Button
							:label="__('Clear Filters')"
							class="w-full sm:w-28"
							@click="Object.assign(filter, getDefaultFilter(true))"
						/>
						<Button
							:label="__('Search')"
							variant="solid"
							class="w-full sm:w-28"
							@click="openSearchPage"
						/>
					</div>
				</template>
				<div v-else-if="results?.data?.[0]?.length" class="p-2">
					<div
						v-for="(result, idx) in results.data[0]"
						:key="idx"
						class="hover:bg-surface-gray-1 group flex rounded p-2 hover:cursor-pointer"
						@click="openThread(result.thread_id)"
					>
						<div class="mr-2 space-y-1 truncate">
							<p class="truncate text-base font-semibold">
								{{ result.subject || __('[No subject]') }}
							</p>
							<p class="truncate text-sm">{{ getInterlocutors(result) }}</p>
							<div
								v-for="m in result.mailboxes"
								:key="m.mailbox_id"
								class="bg-surface-gray-2 group-hover:bg-surface-gray-3 mr-1.5 inline-flex rounded p-1 text-xs"
							>
								{{ m.mailbox_name }}
							</div>
						</div>
						<div
							class="text-ink-gray-4 ml-auto flex shrink-0 flex-col justify-between text-xs"
						>
							<span>{{ getFormattedDate(result.received_at) }}</span>
							<div
								v-if="noOfAttachments(result)"
								class="ml-auto flex items-center space-x-1"
							>
								<Paperclip class="text-ink-gray-4 h-3.5 w-3.5" />
								<span>{{ noOfAttachments(result) }}</span>
							</div>
						</div>
					</div>
					<div
						v-if="results.data[1] > 5"
						class="text-ink-gray-4 my-2 text-center text-sm"
					>
						{{ __('Showing top 5 results. ') }}
						<a class="cursor-pointer hover:underline" @click="openSearchPage">
							{{ __('View more.') }}
						</a>
					</div>
				</div>
				<div
					v-else-if="!results?.loading && results?.data?.[1] === 0"
					class="text-ink-gray-4 py-4 text-center text-sm"
				>
					{{ __('No results found for the given query.') }}
				</div>
			</div>
		</template>
	</component>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import { ChevronLeft, Paperclip, Search, SlidersHorizontal } from 'lucide-vue-next'
import { Button, Dialog, FormControl, createResource } from 'frappe-ui'

import { getAttachmentOptions, getReadStatusOptions } from '@/constants'
import { getFormattedDate } from '@/utils'
import { useScreenSize } from '@/utils/composables'
import { userStore } from '@/stores/user'
import SearchMobileLayout from '@/components/SearchMobileLayout.vue'

import type { Recipient } from '@/types'

const show = defineModel<boolean>()

const { account, mailboxes } = userStore()

const route = useRoute()
const { isMobile } = useScreenSize()

const searchInput = useTemplateRef('searchInput')
watch(show, (val) => {
	if (val) nextTick(() => searchInput.value?.focus())
})

const getDefaultFilter = (reset = false) =>
	Object.fromEntries(
		[
			'text',
			'inMailbox',
			'subject',
			'from',
			'to',
			'cc',
			'bcc',
			'after',
			'before',
			'hasAttachment',
			'isRead',
		].map((key) => [key, reset ? '' : route.query[key] || '']),
	)

const filter = reactive({ ...getDefaultFilter() })
const filteredFilter = computed(() =>
	Object.fromEntries(
		Object.entries(filter)
			.map(([k, v]) => [k, typeof v === 'string' ? v.trim() : v])
			.filter(([, v]) => Boolean(v)),
	),
)
const advancedFiltersLength = computed(
	() => Object.keys(filteredFilter.value).filter((k) => k !== 'text').length,
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
	makeParams: () => ({ account, filter: filteredFilter.value }),
})

const noOfAttachments = (result) =>
	result.attachments?.filter((m) => m.filename && m.disposition === 'attachment').length || 0

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

const openThread = (threadID: string) => {
	router.push({
		name: 'Mail',
		params: { mailbox: 'search', threadID },
		query: filteredFilter.value,
	})
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
