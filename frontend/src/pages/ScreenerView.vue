<template>
	<div class="flex h-full flex-col">
		<header class="flex items-center justify-between border-b px-5 py-3">
			<h2 class="text-xl font-semibold">{{ __('Screener') }}</h2>
			<HeaderActions @reload-mails="senders.reload()" />
		</header>

		<div
			v-if="senders.data?.length"
			class="bg-surface-gray-1 text-ink-gray-7 flex items-center justify-between gap-4 border-b px-5 py-2.5 text-sm"
		>
			<div class="flex min-w-0 items-center gap-2">
				<ShieldCheck class="h-4 w-4 shrink-0" />
				<span class="truncate">
					<b>{{ senderCountLabel }}</b>
					{{ __('Allow them into your inbox, or screen them out to Junk.') }}
				</span>
			</div>
			<div class="flex shrink-0 items-center gap-4">
				<button
					class="text-ink-gray-8 font-medium hover:underline disabled:opacity-50"
					:disabled="!!busyKey"
					@click="allow(allEmails, 'allow:*')"
				>
					{{ __('Allow all') }}
				</button>
				<button
					class="hover:text-ink-gray-8 hover:underline disabled:opacity-50"
					:disabled="!!busyKey"
					@click="screenOut(allEmails, 'screen:*')"
				>
					{{ __('Screen all out') }}
				</button>
			</div>
		</div>

		<div class="flex-1 overflow-y-auto">
			<div v-if="senders.loading && !senders.data" class="text-ink-gray-5 p-5 text-sm">
				{{ __('Loading...') }}
			</div>

			<template v-else-if="senders.data?.length">
				<div v-for="sender in senders.data" :key="sender.from_email" class="border-b">
					<div
						class="hover:bg-surface-gray-1 flex cursor-default items-center gap-4 px-5 py-3"
						@click="toggle(sender.from_email)"
					>
						<Avatar
							:label="
								getFirstAlphabet(sender.from_name) ||
								getFirstAlphabet(sender.from_email)
							"
							size="lg"
							class="shrink-0"
						/>
						<div class="w-52 shrink-0 truncate">
							<div
								class="truncate text-[15px]"
								:class="sender.unread ? 'font-semibold' : 'font-medium'"
							>
								{{ sender.from_name || sender.from_email }}
							</div>
							<div class="text-ink-gray-5 truncate text-sm">
								{{ sender.from_email }}
							</div>
						</div>
						<div class="min-w-0 flex-1 truncate text-sm">
							<span :class="sender.unread ? 'font-semibold' : 'font-medium'">
								{{ sender.subject || __('[No subject]') }}
							</span>
							<span v-if="sender.preview" class="text-ink-gray-5">
								{{ sender.preview }}
							</span>
							<span v-if="sender.count > 1" class="text-ink-gray-5">
								{{ __('({0} messages)', [String(sender.count)]) }}
							</span>
						</div>
						<div class="flex shrink-0 items-center gap-2" @click.stop>
							<Button
								variant="solid"
								:loading="busyKey === `allow:${sender.from_email}`"
								:disabled="!!busyKey"
								@click="allow([sender.from_email], `allow:${sender.from_email}`)"
							>
								<template #prefix><Check class="h-4 w-4" /></template>
								{{ __('Allow') }}
							</Button>
							<Button
								variant="subtle"
								:loading="busyKey === `screen:${sender.from_email}`"
								:disabled="!!busyKey"
								@click="
									screenOut([sender.from_email], `screen:${sender.from_email}`)
								"
							>
								<template #prefix><X class="h-4 w-4" /></template>
								{{ __('Screen out') }}
							</Button>
						</div>
						<MailDate
							:datetime="sender.received_at"
							:in-list="true"
							class="text-ink-gray-5 w-16 shrink-0 text-right text-sm"
						/>
					</div>

					<div v-if="expanded === sender.from_email" class="bg-surface-gray-1 px-5 pb-3">
						<div v-if="senderMails.loading" class="text-ink-gray-5 py-2 text-sm">
							{{ __('Loading messages...') }}
						</div>
						<div
							v-for="mail in senderMails.data"
							v-else
							:key="mail.id"
							class="border-outline-gray-1 flex items-start gap-3 border-t py-2 first:border-t-0"
						>
							<div class="min-w-0 flex-1">
								<div class="truncate text-sm font-medium">
									{{ mail.subject || __('[No subject]') }}
								</div>
								<div class="text-ink-gray-5 truncate text-sm">
									{{ mail.preview || __('— No message body —') }}
								</div>
							</div>
							<MailDate
								:datetime="mail.received_at"
								:in-list="true"
								class="text-ink-gray-5 shrink-0 text-sm"
							/>
						</div>
					</div>
				</div>
			</template>

			<div
				v-else
				class="text-ink-gray-5 flex flex-col items-center justify-center gap-2 p-16"
			>
				<ShieldCheck class="h-8 w-8" />
				<p class="text-base font-medium">{{ __('Your screener is empty.') }}</p>
				<p class="text-sm">
					{{ __('New senders will appear here for you to allow or screen out.') }}
				</p>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, ShieldCheck, X } from 'lucide-vue-next'
import { Avatar, Button, createResource } from 'frappe-ui'

import { getFirstAlphabet, raiseToast } from '@/utils'
import { userStore } from '@/stores/user'
import HeaderActions from '@/components/HeaderActions.vue'
import MailDate from '@/components/MailDate.vue'

import type { ScreeningSender } from '@/types'

const store = userStore()

const senders = createResource({
	url: 'mail.api.mail.get_screening_senders',
	makeParams: () => ({ account: store.account }),
	auto: true,
})

const allEmails = computed(() => (senders.data ?? []).map((s: ScreeningSender) => s.from_email))

const senderCountLabel = computed(() => {
	const n = senders.data?.length ?? 0
	return n === 1 ? __('1 first-time sender.') : __('{0} first-time senders.', [String(n)])
})

// One sender can be expanded at a time to reveal all of their screened messages.
const expanded = ref('')
const senderMails = createResource({
	url: 'mail.api.mail.get_screening_sender_mails',
	makeParams: ({ from_email }: { from_email: string }) => ({
		account: store.account,
		from_email,
	}),
})

const toggle = (fromEmail: string) => {
	if (expanded.value === fromEmail) {
		expanded.value = ''
		return
	}
	expanded.value = fromEmail
	senderMails.submit({ from_email: fromEmail })
}

// `busyKey` is `${action}:${email}` for a single row, or `${action}:*` for the bulk actions, so the
// clicked button shows a spinner while every other action button is disabled.
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
		if (expanded.value && fromEmails.includes(expanded.value)) expanded.value = ''
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
		fromEmails.length === 1 ? __('Sender screened out.') : __('Senders screened out.'),
	)
</script>
