<template>
	<!-- Single-cell root so the Compose FAB can overlay the list. -->
	<GridLayout class="bg-surface-white">
		<GridLayout rows="auto, *">
			<!-- ── Header ── -->
			<GridLayout
				row="0"
				columns="auto, *, auto"
				height="52"
				class="px-1"
				:marginTop="safeTop"
			>
				<GridLayout
					col="0"
					class="h-10 w-10"
					verticalAlignment="center"
					@tap="$emit('open-drawer')"
				>
					<Label
						:text="lucide('menu')"
						class="font-lucide text-ink-gray-7 text-2xl"
						horizontalAlignment="center"
						verticalAlignment="center"
						marginTop="2"
					/>
				</GridLayout>
				<StackLayout col="1" orientation="horizontal" verticalAlignment="center">
					<Label
						:text="mailbox.label"
						class="text-ink-gray-9 ml-1 text-2xl font-bold"
						verticalAlignment="center"
						textWrap="false"
					/>
					<Label
						v-if="countLabel"
						:text="countLabel"
						class="text-ink-gray-5 ml-2 text-sm"
						verticalAlignment="bottom"
						textWrap="false"
					/>
				</StackLayout>
				<GridLayout
					col="2"
					class="h-10 w-10"
					verticalAlignment="center"
					@tap="flash(__('Search coming soon'))"
				>
					<Label
						:text="lucide('search')"
						class="font-lucide text-ink-gray-7 text-xl"
						horizontalAlignment="center"
						verticalAlignment="center"
						marginTop="2"
					/>
				</GridLayout>
			</GridLayout>

			<!-- ── List / states ── -->
			<GridLayout row="1">
				<PullToRefresh v-if="threads.length" @refresh="onPullRefresh">
					<ScrollView @scroll="onScroll">
						<StackLayout>
							<ThreadRow
								v-for="thread in threads"
								:key="thread.thread_id"
								:thread="thread"
								:mailbox-ids="store.mailboxIds"
								@open="openThread(thread)"
								@star="toggleStar(thread)"
							/>
							<!-- footer: loading more / end-of-list hint -->
							<StackLayout class="py-5">
								<ActivityIndicator v-if="loadingMore" busy="true" />
								<Label
									v-else-if="reachedEnd"
									:text="__('No more messages')"
									class="text-ink-gray-4 text-xs"
									textAlignment="center"
								/>
							</StackLayout>
							<StackLayout :height="safeBottom + 80" />
						</StackLayout>
					</ScrollView>
				</PullToRefresh>

				<!-- initial loading -->
				<StackLayout
					v-else-if="loading"
					verticalAlignment="center"
					horizontalAlignment="center"
				>
					<ActivityIndicator busy="true" />
				</StackLayout>

				<!-- error -->
				<StackLayout
					v-else-if="error"
					verticalAlignment="center"
					horizontalAlignment="center"
					class="px-10"
				>
					<Label
						:text="__('Couldn’t load messages')"
						class="text-ink-gray-8 text-lg font-bold"
						textAlignment="center"
					/>
					<Label
						:text="error"
						class="text-ink-gray-5 mt-1 text-sm"
						textAlignment="center"
						textWrap="true"
					/>
					<GridLayout
						class="bg-surface-gray-2 mt-4 rounded-lg px-5 py-2.5"
						@tap="refresh"
					>
						<Label :text="__('Retry')" class="text-ink-gray-8 font-semibold" />
					</GridLayout>
				</StackLayout>

				<!-- empty -->
				<StackLayout
					v-else
					verticalAlignment="center"
					horizontalAlignment="center"
					class="px-10"
				>
					<GridLayout class="bg-surface-gray-2 h-16 w-16 rounded-2xl">
						<Label
							:text="lucide('inbox')"
							class="font-lucide text-ink-gray-4 text-3xl"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<Label
						:text="__('Nothing here')"
						class="text-ink-gray-8 mt-3.5 text-lg font-bold"
						textAlignment="center"
					/>
					<Label
						:text="__('This folder is empty.')"
						class="text-ink-gray-5 mt-1 text-sm"
						textAlignment="center"
					/>
				</StackLayout>
			</GridLayout>
		</GridLayout>

		<!-- ── Compose FAB ── -->
		<StackLayout
			orientation="horizontal"
			class="bg-surface-gray-7 rounded-full py-3.5 pl-4 pr-5"
			horizontalAlignment="right"
			verticalAlignment="bottom"
			marginRight="18"
			:marginBottom="safeBottom + 18"
			@tap="flash(__('Compose coming soon'))"
		>
			<Label
				:text="lucide('square-pen')"
				class="font-lucide text-lg text-white"
				verticalAlignment="center"
			/>
			<Label
				:text="__('Compose')"
				class="ml-2 font-semibold text-white"
				verticalAlignment="center"
			/>
		</StackLayout>
	</GridLayout>
</template>

<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'

import { selectedThread, selectedThreadMailbox } from '@/state/selectedThread'
import { useApi } from '@/utils/api'
import { lucide } from '@/utils/lucide'
import { safeAreaBottom, safeAreaTop } from '@/utils/safeArea'
import { userStore } from '@/stores/user'
import ThreadRow from '@/components/ThreadRow.vue'

import type { ActiveMailbox } from '@/types/navigation'
import type { Thread } from '@mail/types'
import type { ScrollEventData } from '@nativescript/core'

const props = defineProps<{ mailbox: ActiveMailbox }>()
const emit = defineEmits<{ 'open-drawer': []; 'open-thread': [] }>()

const store = userStore()
const api = useApi()
const flash = inject<(msg: string) => void>('flash', () => {})

const safeTop = safeAreaTop()
const safeBottom = safeAreaBottom()

const PAGE_SIZE = 50

const threads = ref<Thread[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const reachedEnd = ref(false)
const error = ref<string | null>(null)

let limit = PAGE_SIZE
// Guards against a slow response for a previous mailbox overwriting the current.
let loadToken = 0

const countLabel = computed(() =>
	props.mailbox.total != null ? __('{0} threads', [props.mailbox.total.toLocaleString()]) : '',
)

async function load(initial: boolean) {
	if (!store.account) return
	const token = ++loadToken
	if (initial) {
		loading.value = true
		limit = PAGE_SIZE
		reachedEnd.value = false
	} else {
		loadingMore.value = true
	}
	error.value = null
	try {
		const data = await api.call<[Thread[], string]>('mail.api.mail.get_threads', {
			account: store.account,
			mailbox: props.mailbox.id,
			limit,
		})
		if (token !== loadToken) return
		const list = data?.[0] ?? []
		threads.value = list
		reachedEnd.value = list.length < limit
	} catch (e) {
		if (token !== loadToken) return
		error.value = (e as { message?: string })?.message ?? __('Failed to load messages')
	} finally {
		if (token === loadToken) {
			loading.value = false
			loadingMore.value = false
		}
	}
}

function refresh() {
	load(true)
}

// Pull-to-refresh: reload, then stop the spinner.
function onPullRefresh(args: { object: { refreshing: boolean } }) {
	const ptr = args.object
	load(true).finally(() => (ptr.refreshing = false))
}

function loadMore() {
	if (loading.value || loadingMore.value || reachedEnd.value) return
	limit += PAGE_SIZE
	load(false)
}

// Load more when the user nears the bottom of the list.
function onScroll(args: ScrollEventData) {
	const view = args.object as unknown as { scrollableHeight: number }
	if (view.scrollableHeight - args.scrollY < 600) loadMore()
}

// Hand the thread (and the mailbox it was opened from) to the detail page, which
// marks it seen on open — so it happens however the user reaches the mail.
function openThread(thread: Thread) {
	selectedThread.value = thread
	selectedThreadMailbox.value = props.mailbox.id
	emit('open-thread')
}

function toggleStar(thread: Thread) {
	const next = thread.flagged ? 0 : 1
	thread.flagged = next
	api.call('mail.api.mail.set_flagged', {
		account: store.account,
		ids: [thread.id],
		flagged: !!next,
	}).catch(() => (thread.flagged = next ? 0 : 1))
}

// Reset and reload whenever the selected mailbox changes.
watch(
	() => props.mailbox.id,
	() => {
		threads.value = []
		load(true)
	},
	{ immediate: true },
)
</script>
