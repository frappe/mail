<template>
	<div class="flex h-full flex-col">
		<header class="flex items-center justify-between border-b px-5 py-2.5">
			<Breadcrumbs :items="[{ label: __('Screener') }]" />
			<HeaderActions @reload-mails="senders.reload()" />
		</header>

		<div class="flex-1 overflow-y-auto">
			<div class="pb-20">
				<!-- Count bar — matches the mailbox "All Mails" toolbar height/style. -->
				<div class="text-ink-gray-5 flex min-h-[49px] items-center border-b px-5">
					{{ waitingLabel }}
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
						class="flex items-stretch gap-12 border-b px-5 py-2.5"
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
									class="text-ink-gray-5 font-medium hover:underline disabled:opacity-40"
									:disabled="!!busyKey"
									@click="
										screenOut(
											[sender.from_email],
											`screen:${sender.from_email}`,
										)
									"
								>
									{{ __('Block') }}
								</button>
								<button
									class="text-ink-gray-8 font-medium hover:underline disabled:opacity-40"
									:disabled="!!busyKey"
									@click="
										allow([sender.from_email], `allow:${sender.from_email}`)
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
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Breadcrumbs, createResource, usePageMeta } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'
import HeaderActions from '@/components/HeaderActions.vue'
import MailDate from '@/components/MailDate.vue'

const store = userStore()

const senders = createResource({
	url: 'mail.api.mail.get_screening_senders',
	makeParams: () => ({ account: store.account }),
	auto: true,
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
/* Rows lift and fade as they leave the ledger. */
.sc-leave-active {
	transition:
		opacity 0.22s ease,
		transform 0.22s ease;
}
.sc-leave-to {
	opacity: 0;
	transform: translateY(-6px);
}
</style>
