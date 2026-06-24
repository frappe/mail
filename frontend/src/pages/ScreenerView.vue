<template>
	<div v-if="screeningEnabled" class="flex h-full flex-col">
		<header class="flex items-center justify-between border-b px-3 py-2.5 sm:px-5">
			<div class="flex items-center space-x-2">
				<Button v-if="isMobile" icon="menu" variant="ghost" @click="openSidebar" />
				<Breadcrumbs :items="[{ label: __('Screener') }]" />
			</div>
			<HeaderActions @reload-mails="senders.reload()" />
		</header>

		<div class="relative flex flex-1 overflow-hidden">
			<!-- Loading the sender list — centered like the mailbox empty/loading states. -->
			<div
				v-if="senders.loading && !senders.data"
				class="flex h-[calc(100dvh-6.1rem)] w-full flex-col items-center justify-center"
			>
				<div class="text-ink-gray-5 flex items-center space-x-2">
					<LoaderCircle class="h-5 w-5 animate-spin" />
					<span>{{ __('Loading...') }}</span>
				</div>
			</div>

			<!-- Nothing to screen — one centered empty screen, no split. -->
			<div
				v-else-if="!senders.data?.length"
				class="text-ink-gray-5 flex h-[calc(100dvh-6.1rem)] w-full flex-col items-center justify-center"
			>
				<NoMails class="text-ink-gray-2 mb-2 h-16 w-16" />
				<p>{{ __('You have no new senders to screen.') }}</p>
			</div>

			<template v-else>
				<!-- Sender list -->
				<div
					class="flex flex-col overflow-y-auto"
					:class="!isMobile && showReadingPane ? 'w-1/3 border-r' : 'w-full'"
				>
					<div class="pb-20">
						<!-- Count bar — matches the mailbox "All Mails" toolbar height/style. -->
						<div class="flex min-h-[49px] items-center justify-between border-b px-5">
							<span class="text-ink-gray-5 truncate">{{ waitingLabel }}</span>
							<Button
								:label="__('Clear All')"
								variant="ghost"
								class="-mr-2"
								@click="showClearAll = true"
							/>
						</div>

						<div
							v-for="sender in senders.data"
							:key="sender.from_email"
							:data-sender-email="sender.from_email"
							class="sm:hover:bg-surface-gray-1 flex cursor-default select-none items-stretch gap-4 border-b px-5 py-2.5"
							:class="{
								'!bg-surface-blue-1': openSender?.from_email === sender.from_email,
							}"
							@click="selectSender(sender)"
						>
							<div class="min-w-0 flex-1 space-y-1">
								<div class="flex min-w-0 items-baseline gap-2">
									<span
										class="text-ink-gray-8 truncate text-[15px] !font-semibold sm:text-base"
									>
										{{ sender.from_name || sender.from_email }}
									</span>
									<span class="text-ink-gray-5 truncate text-[13px]">
										{{ sender.from_email }}
									</span>
								</div>
								<div
									class="text-ink-gray-8 truncate text-sm !font-semibold !leading-[1.5]"
								>
									{{ sender.subject || __('[No subject]') }}
								</div>
								<div
									v-if="sender.preview || sender.count > 1"
									class="text-ink-gray-5 truncate text-sm !leading-[1.5]"
								>
									<span v-if="sender.preview">{{ sender.preview }}</span>
									<span v-if="sender.count > 1">
										{{ sender.preview ? ' · ' : ''
										}}{{ __('{0} messages', [String(sender.count)]) }}
									</span>
								</div>
							</div>

							<!-- Time top-right, persistent Block / Allow parked bottom-right -->
							<div class="flex shrink-0 flex-col items-end justify-between">
								<MailDate
									:datetime="sender.received_at"
									:in-list="true"
									class="text-ink-gray-4 whitespace-nowrap pt-px text-xs tabular-nums"
								/>
								<div class="-mr-2 flex gap-2">
									<Button
										variant="outline"
										:label="__('Block')"
										@click.stop="screenOut([sender.from_email])"
									/>
									<Button
										variant="outline"
										:label="__('Allow')"
										@click.stop="allow([sender.from_email])"
									/>
								</div>
							</div>
						</div>
					</div>
				</div>

				<!-- Read-only thread preview — split when the reading pane is on, full-width otherwise -->
				<div
					class="bg-surface-white flex flex-col"
					:class="{
						'w-2/3': !isMobile && showReadingPane,
						'absolute bottom-0 left-0 right-0 top-0': !isMobile && !showReadingPane,
						'fixed inset-0': isMobile,
						hidden: (isMobile || !showReadingPane) && !openSender,
					}"
				>
					<template v-if="openSender">
						<!-- Subject + Block/Allow; back button only when the preview owns the whole pane -->
						<div
							class="bg-surface-white sticky top-0 z-10 flex shrink-0 items-center justify-between gap-3 border-b p-2.5 sm:px-5"
						>
							<div class="flex min-w-0 items-center">
								<Button
									variant="ghost"
									class="-ml-1.5 mr-2 shrink-0"
									@click="closeSender"
								>
									<template #icon>
										<ChevronLeft class="icon" />
									</template>
								</Button>
								<h2 class="truncate font-semibold leading-5">
									{{ openSender.subject || __('[No subject]') }}
								</h2>
							</div>
							<div class="flex shrink-0 gap-2">
								<Button
									variant="outline"
									:label="__('Block')"
									@click="screenOut([openSender.from_email])"
								/>
								<Button
									variant="solid"
									:label="__('Allow')"
									@click="allow([openSender.from_email])"
								/>
							</div>
						</div>

						<MailThreadSkeleton v-if="previewLoading" />
						<MailThread
							v-else-if="previewMails?.length"
							:key="openSender.from_email"
							class="min-h-0 flex-1"
							readonly
							mailbox=""
							:thread-i-d="openSender.from_email"
							:threads="[]"
							:messages="previewMails"
						/>
					</template>

					<div v-else class="flex-1 overflow-hidden">
						<div
							class="bg-surface-gray-1 m-5 flex h-[calc(100%-2.9em)] items-center justify-center rounded-md"
						>
							<div class="flex flex-col items-center space-y-3">
								<NoMails class="text-ink-gray-2 h-16 w-16" />
								<p class="text-ink-gray-4">
									{{ __('Select a sender to view their emails.') }}
								</p>
							</div>
						</div>
					</div>
				</div>
			</template>
		</div>

		<Dialog v-model="showClearAll" :options="clearAllOptions" />
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronLeft, LoaderCircle } from 'lucide-vue-next'
import { Breadcrumbs, Button, Dialog, createResource, usePageMeta } from 'frappe-ui'

import { raiseToast, shouldIgnoreKeypress } from '@/utils'
import { useScreenSize, useSidebar } from '@/utils/composables'
import { userStore } from '@/stores/user'
import HeaderActions from '@/components/HeaderActions.vue'
import NoMails from '@/components/Icons/NoMails.vue'
import MailDate from '@/components/MailDate.vue'
import MailThread from '@/components/MailThread.vue'
import MailThreadSkeleton from '@/components/MailThreadSkeleton.vue'

import type { Mail, MailboxData, ScreeningSender } from '@/types'

const store = userStore()
const router = useRouter()
const { isMobile } = useScreenSize()
const { openSidebar } = useSidebar()

const showReadingPane = computed(() => !!store.userResource?.data?.show_reading_pane)

// The Screener only exists when screening is enabled. If it's off, render nothing and send the user to
// their inbox (the route is still reachable by URL even though the sidebar hides it).
const screeningEnabled = computed(
	() =>
		!!store.userResource?.data?.accounts?.find((a) => a.id === store.accountId)
			?.enable_screening,
)
watch(
	() => [!!store.userResource?.data, screeningEnabled.value, store.mailboxIds.inbox] as const,
	([ready, enabled, inboxId]) => {
		if (ready && !enabled && inboxId)
			router.replace({
				name: 'Mailbox',
				params: { accountId: store.accountId, mailbox: inboxId },
			})
	},
	{ immediate: true },
)

// The sender whose mail is open in the read-only preview, and that sender's messages.
const openSender = ref<ScreeningSender | null>(null)
const senderMails = createResource({
	url: 'mail.api.mail.get_screening_sender_mails',
	makeParams: () => ({ account_id: store.accountId, from_email: openSender.value?.from_email }),
})

// The preview reads `previewMails`, not the resource's `.data`: fast navigation fires several fetches
// at once and the resource flips `loading` off on the first reply that lands, so an out-of-order reply
// could otherwise leak the previous sender in (and the thread then appends the next one onto it). Each
// fetch carries a token; only the most recent one is applied.
const previewMails = ref<Mail[]>()
const previewLoading = ref(false)
let previewToken = 0

const selectSender = (sender: ScreeningSender) => {
	if (openSender.value?.from_email === sender.from_email) return
	openSender.value = sender

	const token = ++previewToken
	previewMails.value = undefined
	previewLoading.value = true
	;(senderMails.reload() as Promise<Mail[]>)
		.then((mails) => {
			if (token !== previewToken) return
			previewMails.value = mails ?? []
			previewLoading.value = false
		})
		.catch(() => {
			if (token === previewToken) previewLoading.value = false
		})
}

const closeSender = () => {
	openSender.value = null
}

const senders = createResource({
	url: 'mail.api.mail.get_screening_senders',
	makeParams: () => ({ account_id: store.accountId }),
	auto: true,
})

// Once a mail is open, ↑/↓ (or k/j) step to the previous/next sender and Esc closes it. Else inert.
const handleKeydown = (e: KeyboardEvent) => {
	if (!openSender.value || shouldIgnoreKeypress(e)) return
	const key = e.key.toLowerCase()

	if (key === 'escape') {
		e.preventDefault()
		closeSender()
		return
	}

	const offset =
		key === 'arrowup' || key === 'k' ? -1 : key === 'arrowdown' || key === 'j' ? 1 : 0
	if (!offset) return

	e.preventDefault()
	const list = senders.data ?? []
	const cur = list.findIndex(
		(s: ScreeningSender) => s.from_email === openSender.value!.from_email,
	)
	const next = list[cur + offset]
	if (!next) return

	selectSender(next)
	nextTick(() =>
		document
			.querySelector(`[data-sender-email="${next.from_email}"]`)
			?.scrollIntoView({ block: 'nearest' }),
	)
}

// Poll the Screening folder's count and only refetch the (heavier) sender list when it changes — the
// same cheap-count-then-reload approach the mailbox uses, so a quiet screener isn't reloaded every tick.
const screeningCount = () =>
	store.mailboxes.data?.find((m: MailboxData) => m.id === store.mailboxIds.screening)
		?.total_threads

const pollForChanges = async () => {
	const prev = screeningCount()
	await store.mailboxes.reload()
	if (screeningCount() !== prev) senders.reload()
}

let pollInterval: ReturnType<typeof setInterval>

onMounted(() => {
	window.addEventListener('keydown', handleKeydown)
	pollInterval = setInterval(pollForChanges, 30000)
})

onUnmounted(() => {
	window.removeEventListener('keydown', handleKeydown)
	clearInterval(pollInterval)
})

usePageMeta(() => {
	const n = senders.data?.length ?? 0
	return { title: n ? `(${n}) ${__('Screener')}` : __('Screener') }
})

const waitingLabel = computed(() => {
	const n = senders.data?.length ?? 0
	return n === 1 ? __('1 new sender.') : __('{0} new senders.', [String(n)])
})

const allowResource = createResource({
	url: 'mail.api.mail.allow_screening_senders',
	makeParams: ({ from_emails }: { from_emails: string[] }) => ({
		account_id: store.accountId,
		from_emails,
	}),
})

const screenOutResource = createResource({
	url: 'mail.api.mail.screen_out_senders',
	makeParams: ({ from_emails }: { from_emails: string[] }) => ({
		account_id: store.accountId,
		from_emails,
	}),
})

const runAction = async (resource: typeof allowResource, fromEmails: string[]) => {
	if (!fromEmails.length) return

	// When acting on the sender open in the detail view, line up the next one down so you can triage
	// straight through — resolved before the optimistic removal.
	const list = senders.data ?? []
	const actingOnOpen = !!openSender.value && fromEmails.includes(openSender.value.from_email)
	let nextSender: ScreeningSender | undefined
	if (actingOnOpen) {
		const idx = list.findIndex(
			(s: ScreeningSender) => s.from_email === openSender.value!.from_email,
		)
		nextSender = list
			.slice(idx + 1)
			.find((s: ScreeningSender) => !fromEmails.includes(s.from_email))
	}

	// Optimistically drop the acted senders so the rows leave immediately and every other row stays
	// interactive. The row leaving is the only success feedback (no toast); only failures are surfaced
	// — with a resync to bring the rows back.
	senders.data = list.filter((s: ScreeningSender) => !fromEmails.includes(s.from_email))

	// Advance to the next sender (or close the preview if there's nothing below).
	if (actingOnOpen) {
		if (nextSender) selectSender(nextSender)
		else closeSender()
	}

	try {
		await resource.submit({ from_emails: fromEmails })
		// Allowing/screening senders changes inbox/junk counts too.
		store.mailboxes.reload()
	} catch (error) {
		senders.reload()
		raiseToast((error as Error).message || __('Action failed.'), 'error')
	}
}

const allow = (fromEmails: string[]) => runAction(allowResource, fromEmails)
const screenOut = (fromEmails: string[]) => runAction(screenOutResource, fromEmails)

// Clear All empties the queue without judging anyone: it moves all screened mail to the inbox but
// creates no Block/Allow rule, so a mixed queue can't accidentally whitelist spam or block a real sender.
const showClearAll = ref(false)

const clearAllResource = createResource({
	url: 'mail.api.mail.move_screening_mails_to_inbox',
	makeParams: () => ({ account_id: store.accountId }),
	onSuccess: () => {
		senders.data = []
		closeSender()
		showClearAll.value = false
		store.mailboxes.reload()
		raiseToast(__('Unscreened messages moved to Inbox.'))
	},
})

const clearAllOptions = computed(() => ({
	title: __('Clear the Screener?'),
	message: __(
		'This will move current unscreened messages to your Inbox. Future emails from these senders will still go to the Screener.',
	),
	actions: [
		{
			label: __('Move to Inbox'),
			variant: 'solid',
			onClick: () => clearAllResource.submit(),
			loading: clearAllResource.loading,
		},
	],
}))
</script>
