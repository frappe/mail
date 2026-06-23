<template>
	<div class="flex h-full flex-col">
		<header class="flex items-center justify-between border-b px-3 py-2.5 sm:px-5">
			<div class="flex items-center space-x-2">
				<Button v-if="isMobile" icon="menu" variant="ghost" @click="openSidebar" />
				<Breadcrumbs :items="[{ label: __('Screener') }]" />
			</div>
			<HeaderActions @reload-mails="senders.reload()" />
		</header>

		<div class="relative flex flex-1 overflow-hidden">
			<!-- Sender list -->
			<div
				class="flex flex-col overflow-y-auto"
				:class="!isMobile && showReadingPane ? 'w-1/3 border-r' : 'w-full'"
			>
				<div class="pb-20">
					<!-- Count bar — matches the mailbox "All Mails" toolbar height/style. -->
					<div class="flex min-h-[49px] items-center border-b px-5">
						<span class="text-ink-gray-5 truncate">{{ waitingLabel }}</span>
					</div>

					<div
						v-if="senders.loading && !senders.data"
						class="text-ink-gray-5 px-5 py-6 text-sm"
					>
						{{ __('Loading...') }}
					</div>

					<div
						v-else-if="!senders.data?.length"
						class="text-ink-gray-5 px-5 py-16 text-center text-[15px]"
					>
						{{ __('Nothing left to screen.') }}
					</div>

					<TransitionGroup v-else name="sc" tag="div">
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
								<div class="flex gap-5">
									<button
										class="screener-action text-ink-gray-5"
										:disabled="!!busyKey"
										@click.stop="
											screenOut(
												[sender.from_email],
												`screen:${sender.from_email}`,
											)
										"
									>
										{{ __('Block') }}
									</button>
									<button
										class="screener-action text-ink-gray-8"
										:disabled="!!busyKey"
										@click.stop="
											allow(
												[sender.from_email],
												`allow:${sender.from_email}`,
											)
										"
									>
										{{ __('Allow') }}
									</button>
								</div>
							</div>
						</div>
					</TransitionGroup>
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
							<Button variant="ghost" class="mr-2 shrink-0" @click="closeSender">
								<template #icon>
									<ChevronLeft class="text-ink-gray-7 h-4 w-4" />
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
								:loading="busyKey === `screen:${openSender.from_email}`"
								:disabled="!!busyKey"
								@click="
									screenOut(
										[openSender.from_email],
										`screen:${openSender.from_email}`,
									)
								"
							/>
							<Button
								variant="solid"
								:label="__('Allow')"
								:loading="busyKey === `allow:${openSender.from_email}`"
								:disabled="!!busyKey"
								@click="
									allow(
										[openSender.from_email],
										`allow:${openSender.from_email}`,
									)
								"
							/>
						</div>
					</div>

					<div v-if="senderMails.loading" class="text-ink-gray-5 px-5 py-6 text-sm">
						{{ __('Loading...') }}
					</div>
					<MailThread
						v-else-if="senderMails.data?.length"
						:key="openSender.from_email"
						class="min-h-0 flex-1"
						readonly
						mailbox=""
						:thread-i-d="openSender.from_email"
						:threads="[]"
						:messages="senderMails.data"
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
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ChevronLeft } from 'lucide-vue-next'
import { Breadcrumbs, Button, createResource, usePageMeta } from 'frappe-ui'

import { raiseToast, shouldIgnoreKeypress } from '@/utils'
import { useScreenSize, useSidebar } from '@/utils/composables'
import { userStore } from '@/stores/user'
import HeaderActions from '@/components/HeaderActions.vue'
import NoMails from '@/components/Icons/NoMails.vue'
import MailDate from '@/components/MailDate.vue'
import MailThread from '@/components/MailThread.vue'

import type { MailboxData, ScreeningSender } from '@/types'

const store = userStore()
const { isMobile } = useScreenSize()
const { openSidebar } = useSidebar()

const showReadingPane = computed(() => !!store.userResource?.data?.show_reading_pane)

// The sender whose mail is open in the read-only preview, and that sender's messages.
const openSender = ref<ScreeningSender | null>(null)
const senderMails = createResource({
	url: 'mail.api.mail.get_screening_sender_mails',
	makeParams: () => ({ account: store.account, from_email: openSender.value?.from_email }),
})

const selectSender = (sender: ScreeningSender) => {
	if (openSender.value?.from_email === sender.from_email) return
	openSender.value = sender
	senderMails.reload()
}

const closeSender = () => {
	openSender.value = null
}

const senders = createResource({
	url: 'mail.api.mail.get_screening_senders',
	makeParams: () => ({ account: store.account }),
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
	return n === 1
		? __('1 first-time sender waiting to be screened.')
		: __('{0} first-time senders waiting to be screened.', [String(n)])
})

// `busyKey` is `${action}:${email}` for the row being acted on; every action button is disabled
// while one is in flight.
const busyKey = ref('')

const allowResource = createResource({
	url: 'mail.api.mail.allow_screening_senders',
	makeParams: ({ from_emails }: { from_emails: string[] }) => ({
		account: store.account,
		from_emails,
	}),
})

const screenOutResource = createResource({
	url: 'mail.api.mail.screen_out_senders',
	makeParams: ({ from_emails }: { from_emails: string[] }) => ({
		account: store.account,
		from_emails,
	}),
})

const runAction = async (
	resource: typeof allowResource,
	fromEmails: string[],
	key: string,
	success: string,
) => {
	if (!fromEmails.length || busyKey.value) return
	busyKey.value = key
	try {
		await resource.submit({ from_emails: fromEmails })
		raiseToast(success)
		// The open preview's sender may have just been allowed/blocked away — close it.
		if (openSender.value && fromEmails.includes(openSender.value.from_email)) closeSender()
		await senders.reload()
		// Allowing/screening senders changes inbox/junk counts too.
		store.mailboxes.reload()
	} catch (error) {
		raiseToast((error as Error).message || __('Action failed.'), 'error')
	} finally {
		busyKey.value = ''
	}
}

const allow = (fromEmails: string[], key: string) =>
	runAction(
		allowResource,
		fromEmails,
		key,
		fromEmails.length === 1 ? __('Sender allowed.') : __('Senders allowed.'),
	)

const screenOut = (fromEmails: string[], key: string) =>
	runAction(
		screenOutResource,
		fromEmails,
		key,
		fromEmails.length === 1 ? __('Sender blocked.') : __('Senders blocked.'),
	)
</script>

<style scoped>
/* Quiet text actions (Block / Allow) with an expanded hit area — the negative margin offsets the
   padding so the larger click target doesn't shift the layout. */
.screener-action {
	@apply -m-2 p-2 font-medium hover:underline disabled:opacity-40;
}

/* Rows lift and fade as they leave the ledger. */
.sc-leave-active {
	@apply transition-all duration-200 ease-out;
}
.sc-leave-to {
	@apply -translate-y-1.5 opacity-0;
}
</style>
