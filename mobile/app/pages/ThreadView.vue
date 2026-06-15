<template>
	<Page actionBarHidden="true">
		<GridLayout class="bg-surface-white">
			<GridLayout rows="auto, *, auto">
				<!-- top bar: back + actions (reading-only; actions are placeholders) -->
				<GridLayout
					row="0"
					columns="auto, *, auto, auto, auto"
					class="border-outline-gray-1 border-b px-1 py-2"
					:marginTop="safeTop"
				>
					<GridLayout col="0" class="h-10 w-10" @tap="goBack">
						<Label
							:text="lucide('chevron-left')"
							class="font-lucide text-ink-gray-7 text-2xl"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<GridLayout col="2" class="h-10 w-10" @tap="flash(__('Archive coming soon'))">
						<Label
							:text="lucide('archive')"
							class="font-lucide text-ink-gray-6 text-xl"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<GridLayout col="3" class="h-10 w-10" @tap="flash(__('Delete coming soon'))">
						<Label
							:text="lucide('trash-2')"
							class="font-lucide text-ink-gray-6 text-xl"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
					<GridLayout col="4" class="h-10 w-10" @tap="flash(__('More coming soon'))">
						<Label
							:text="lucide('ellipsis')"
							class="font-lucide text-ink-gray-6 text-xl"
							horizontalAlignment="center"
							verticalAlignment="center"
						/>
					</GridLayout>
				</GridLayout>

				<!-- thread body -->
				<GridLayout row="1">
					<WebView
						v-if="html"
						:src="html"
						@loaded="onWebViewLoaded"
						@loadStarted="onLoadStarted"
					/>

					<StackLayout
						v-else-if="loading"
						verticalAlignment="center"
						horizontalAlignment="center"
					>
						<ActivityIndicator busy="true" />
					</StackLayout>

					<StackLayout
						v-else
						verticalAlignment="center"
						horizontalAlignment="center"
						class="px-10"
					>
						<Label
							:text="__('Couldn’t load this thread')"
							class="text-ink-gray-8 text-lg font-bold"
							textAlignment="center"
						/>
						<Label
							v-if="error"
							:text="error"
							class="text-ink-gray-5 mt-1 text-sm"
							textAlignment="center"
							textWrap="true"
						/>
						<GridLayout
							class="bg-surface-gray-2 mt-4 rounded-lg px-5 py-2.5"
							@tap="load"
						>
							<Label :text="__('Retry')" class="text-ink-gray-8 font-semibold" />
						</GridLayout>
					</StackLayout>
				</GridLayout>

				<!-- bottom action bar (reply / reply-all / forward → compose, #490). Hidden
				     when the last message is a draft (it's already being composed). -->
				<GridLayout
					v-if="!lastIsDraft"
					row="2"
					:columns="showReplyAll ? '*, *, *' : '*, *'"
					class="border-outline-gray-1 border-t px-4 pb-7 pt-3"
					:marginBottom="safeBottom"
				>
					<GridLayout
						col="0"
						class="border-outline-gray-2 mr-1.5 rounded-xl border py-3"
						@tap="onReply"
					>
						<StackLayout orientation="horizontal" horizontalAlignment="center">
							<Label
								:text="lucide('reply')"
								class="font-lucide text-ink-gray-8 text-lg"
								verticalAlignment="center"
							/>
							<Label
								:text="__('Reply')"
								class="text-ink-gray-8 ml-1.5 font-semibold"
								verticalAlignment="center"
							/>
						</StackLayout>
					</GridLayout>
					<GridLayout
						v-if="showReplyAll"
						col="1"
						class="border-outline-gray-2 mx-1.5 rounded-xl border py-3"
						@tap="onReplyAll"
					>
						<StackLayout orientation="horizontal" horizontalAlignment="center">
							<Label
								:text="lucide('reply-all')"
								class="font-lucide text-ink-gray-8 text-lg"
								verticalAlignment="center"
							/>
							<Label
								:text="__('Reply all')"
								class="text-ink-gray-8 ml-1.5 font-semibold"
								verticalAlignment="center"
							/>
						</StackLayout>
					</GridLayout>
					<GridLayout
						:col="showReplyAll ? 2 : 1"
						class="border-outline-gray-2 ml-1.5 rounded-xl border py-3"
						@tap="onForward"
					>
						<StackLayout orientation="horizontal" horizontalAlignment="center">
							<Label
								:text="lucide('forward')"
								class="font-lucide text-ink-gray-8 text-lg"
								verticalAlignment="center"
							/>
							<Label
								:text="__('Forward')"
								class="text-ink-gray-8 ml-1.5 font-semibold"
								verticalAlignment="center"
							/>
						</StackLayout>
					</GridLayout>
				</GridLayout>
			</GridLayout>

			<!-- local toast (this page has its own Frame, outside AppShell's provider) -->
			<Label
				v-if="toast"
				:text="toast"
				class="bg-surface-gray-7 rounded-full px-5 py-3 text-base font-semibold text-white"
				horizontalAlignment="center"
				verticalAlignment="bottom"
				marginBottom="120"
				textWrap="false"
			/>
		</GridLayout>
	</Page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Utils, isAndroid } from '@nativescript/core'
import { $navigateBack, $navigateTo } from 'nativescript-vue'

import { composeContext } from '@/state/composeDraft'
import { selectedThread as thread, selectedThreadMailbox } from '@/state/selectedThread'
import { useApi } from '@/utils/api'
import { buildDraftEdit, buildForward, buildReply, buildReplyAll } from '@/utils/compose'
import { lucide } from '@/utils/lucide'
import { safeAreaBottom, safeAreaTop } from '@/utils/safeArea'
import { buildThreadDocument } from '@/utils/threadHtml'
import { userStore } from '@/stores/user'
import ComposeView from '@/pages/ComposeView.vue'

import type { ComposeMailData, Mail } from '@mail/types'
import type { EventData, LoadEventData } from '@nativescript/core'

const store = userStore()
const api = useApi()
const safeTop = safeAreaTop()
const safeBottom = safeAreaBottom()

const html = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const mails = ref<Mail[]>([])

// Reply-all is offered when the (last) message has recipients besides you —
// mirrors the web MailThread showReplyAll.
const showReplyAll = computed(() => {
	const last = mails.value[mails.value.length - 1]
	if (!last) return false
	return (last.recipients || []).filter((r) => r.type === 'To' || r.type === 'Cc').length > 1
})

// Hide the reply/forward bar when the last message is a draft — the user is already
// composing it (mirrors the web MailThread).
const lastIsDraft = computed(() => !!mails.value.at(-1)?.draft)

// The user's own send-as addresses, used by the reply/reply-all recipient logic.
const userEmails = computed(() => (store.user?.accounts ?? []).map((a) => a._name || a.name))

// Reply/forward act on the latest message in the thread (mirrors the web), building
// the compose pre-fill and handing off to ComposeView via composeContext.
function openCompose(ctx: ComposeMailData) {
	composeContext.value = ctx
	$navigateTo(ComposeView)
}
function onReply() {
	const last = mails.value.at(-1)
	if (last) openCompose(buildReply(last, userEmails.value))
}
function onReplyAll() {
	const last = mails.value.at(-1)
	if (last) openCompose(buildReplyAll(last, userEmails.value))
}
function onForward() {
	const last = mails.value.at(-1)
	if (last) openCompose(buildForward(last))
}

const toast = ref<string | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null
function flash(msg: string) {
	toast.value = msg
	if (toastTimer) clearTimeout(toastTimer)
	toastTimer = setTimeout(() => (toast.value = null), 1800)
}

async function load() {
	const t = thread.value
	if (!t) {
		error.value = __('No thread selected')
		return
	}
	loading.value = true
	error.value = null
	try {
		const data = await api.call<Mail[]>('mail.api.mail.get_thread', {
			account: store.account,
			thread_id: t.thread_id,
		})
		mails.value = data ?? []
		// Use the first message's subject (the original), not the thread's latest.
		html.value = buildThreadDocument(mails.value, mails.value[0]?.subject || t.subject || '')
	} catch (e) {
		error.value = (e as { message?: string })?.message ?? __('Failed to load this thread')
	} finally {
		loading.value = false
	}
}

function onWebViewLoaded(args: EventData) {
	if (!isAndroid) return
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const native = (args.object as any).android
	// Hide Android's on-screen zoom (-/+) widget while keeping pinch-to-zoom.
	const settings = native?.getSettings?.()
	settings?.setBuiltInZoomControls(true)
	settings?.setDisplayZoomControls(false)
	// Render on a software layer so the WebView can be captured in the page
	// transition bitmap — otherwise Android flashes white (then redraws) when
	// navigating back. (1 = android.view.View.LAYER_TYPE_SOFTWARE)
	native?.setLayerType?.(1, null)
}

// Links navigate to an `x-open:` scheme we intercept here, so taps open in the
// system browser instead of inside the sandboxed WebView.
function onLoadStarted(args: LoadEventData) {
	const url = args.url ?? ''
	const view = args.object as unknown as { stopLoading?: () => void }
	if (url.startsWith('x-open:')) {
		view.stopLoading?.()
		const target = decodeURIComponent(url.slice('x-open:'.length))
		if (target) Utils.openUrl(target)
	} else if (url.startsWith('x-edit:')) {
		// "Edit draft" button — open the draft message in the compose screen.
		view.stopLoading?.()
		const mail = mails.value[Number(url.slice('x-edit:'.length))]
		if (mail) openCompose(buildDraftEdit(mail))
	} else if (url.startsWith('x-more:')) {
		// Per-message "more" button — actions land in #490.
		view.stopLoading?.()
		flash(__('More coming soon'))
	}
}

// Mark the thread seen when the detail view opens (path-independent), mutating
// the shared thread object so the list row updates too.
onMounted(() => {
	const t = thread.value
	if (t && !t.seen) {
		t.seen = 1
		api.call('mail.api.mail.set_seen', {
			account: store.account,
			thread_ids: { true: [t.thread_id] },
			mailbox: selectedThreadMailbox.value,
		}).catch(() => (t.seen = 0))
	}
	load()
})

function goBack() {
	$navigateBack()
}
</script>
