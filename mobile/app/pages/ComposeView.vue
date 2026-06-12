<template>
	<Page actionBarHidden="true">
		<GridLayout rows="auto, auto, *" class="bg-surface-white">
			<!-- Header: cancel · title · more · Send -->
			<GridLayout
				row="0"
				columns="auto, *, auto, auto"
				class="px-1 py-2"
				:marginTop="safeTop"
			>
				<GridLayout col="0" class="h-10 w-10" @tap="requestClose">
					<Label
						:text="lucide('x')"
						class="font-lucide text-ink-gray-8 text-2xl"
						horizontalAlignment="center"
						verticalAlignment="center"
					/>
				</GridLayout>
				<Label
					col="1"
					:text="__('Compose Mail')"
					class="text-ink-gray-9 pl-1 text-lg font-bold"
					verticalAlignment="center"
				/>
				<GridLayout col="2" class="h-10 w-10" @tap="sheet = 'more'">
					<Label
						:text="lucide('more-vertical')"
						class="font-lucide text-ink-gray-7 text-2xl"
						horizontalAlignment="center"
						verticalAlignment="center"
					/>
				</GridLayout>
				<GridLayout col="3" class="h-10 w-10" @tap="send">
					<Label
						:text="lucide('send-horizontal')"
						class="font-lucide text-2xl"
						:class="canSend ? 'text-ink-gray-8' : 'text-ink-gray-4'"
						horizontalAlignment="center"
						verticalAlignment="center"
					/>
				</GridLayout>
			</GridLayout>

			<!-- Recipients + subject -->
			<StackLayout row="1">
				<!-- From -->
				<GridLayout columns="auto, *" class="border-outline-gray-1 border-b px-4 py-2.5">
					<Label
						col="0"
						:text="__('From')"
						class="text-ink-gray-5 w-12 text-base"
						verticalAlignment="center"
					/>
					<GridLayout
						col="1"
						columns="auto, auto"
						class="bg-surface-gray-3 rounded-full px-3 py-1.5"
						horizontalAlignment="left"
						@tap="sheet = 'from'"
					>
						<Label
							col="0"
							:text="fromLabel"
							class="text-ink-gray-9 text-sm font-medium"
							verticalAlignment="center"
						/>
						<Label
							col="1"
							:text="lucide('chevron-down')"
							class="font-lucide text-ink-gray-5 ml-1 text-sm"
							verticalAlignment="center"
						/>
					</GridLayout>
				</GridLayout>

				<!-- To (+ Cc/Bcc reveal) -->
				<RecipientField
					v-model="to"
					:label="__('To')"
					:account="fromAccount"
					@pending="toPending = $event"
				>
					<template #trailing>
						<Label
							:text="lucide('chevron-down')"
							class="font-lucide text-ink-gray-5 my-1 ml-1 text-lg"
							:rotate="ccVisible ? 180 : 0"
							verticalAlignment="center"
							@tap="ccOpen = !ccOpen"
						/>
					</template>
				</RecipientField>

				<template v-if="ccVisible">
					<RecipientField v-model="cc" :label="__('Cc')" :account="fromAccount" />
					<RecipientField v-model="bcc" :label="__('Bcc')" :account="fromAccount" />
				</template>

				<!-- Subject -->
				<GridLayout class="border-outline-gray-1 border-b px-4 py-2.5">
					<TextField
						v-model="subject"
						:hint="__('Subject')"
						class="text-ink-gray-9 text-base"
						:class="{ 'font-semibold': subject }"
						@loaded="onSubjectLoaded"
					/>
				</GridLayout>
			</StackLayout>

			<!-- Body (rich text) -->
			<RichTextEditor ref="editor" v-model="body" row="2" />

			<!-- From picker -->
			<ComposeSheet row="0" rowSpan="3" :open="sheet === 'from'" @close="sheet = null">
				<Label
					:text="__('Send as')"
					class="text-ink-gray-4 px-5 pb-1 pt-2 text-xs font-semibold uppercase"
				/>
				<GridLayout
					v-for="a in accounts"
					:key="a.accountName"
					columns="*, auto"
					class="px-5 py-3"
					@tap="selectFrom(a)"
				>
					<StackLayout col="0" verticalAlignment="center">
						<Label :text="a.email" class="text-ink-gray-9 text-base font-semibold" />
						<Label
							:text="a.isPersonal ? __('Personal') : __('Group')"
							class="text-ink-gray-5 mt-0.5 text-sm"
						/>
					</StackLayout>
					<Label
						v-if="a.accountName === fromAccount"
						col="1"
						:text="lucide('check')"
						class="font-lucide text-ink-gray-9 text-lg"
						verticalAlignment="center"
					/>
				</GridLayout>
			</ComposeSheet>

			<!-- More menu -->
			<ComposeSheet row="0" rowSpan="3" :open="sheet === 'more'" @close="sheet = null">
				<ComposeSheetRow icon="save" :label="__('Save draft')" @tap="saveAndClose" />
				<ComposeSheetRow icon="trash-2" :label="__('Discard')" danger @tap="discard" />
			</ComposeSheet>

			<!-- toast -->
			<Label
				v-if="toast"
				row="2"
				:text="toast"
				class="bg-surface-gray-7 mx-6 mb-10 rounded-lg px-4 py-3 text-center text-white"
				verticalAlignment="bottom"
				textWrap="true"
			/>
		</GridLayout>
	</Page>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { isAndroid } from '@nativescript/core'
import { $navigateBack } from 'nativescript-vue'

import { composeContext } from '@/state/composeDraft'
import { useApi } from '@/utils/api'
import { lucide } from '@/utils/lucide'
import { safeAreaTop } from '@/utils/safeArea'
import { userStore } from '@/stores/user'
import ComposeSheet from '@/components/ComposeSheet.vue'
import ComposeSheetRow from '@/components/ComposeSheetRow.vue'
import RecipientField from '@/components/RecipientField.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'

import type { DraftRecipient } from '@mail/types'
import type { EventData } from '@nativescript/core'

const store = userStore()
const api = useApi()
const safeTop = safeAreaTop()

function onSubjectLoaded(args: EventData) {
	// iOS (plain UITextField) has no left inset, so it already aligns with the
	// labels. Android's EditText has an intrinsic left padding that shifts the
	// text right — zero ONLY the left inset (keeping the vertical padding so the
	// row stays the same height as the recipient fields) and drop the underline.
	if (!isAndroid) return
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const et = (args.object as any).android
	if (!et) return
	const top = et.getPaddingTop?.() ?? 0
	const right = et.getPaddingRight?.() ?? 0
	const bottom = et.getPaddingBottom?.() ?? 0
	et.setBackground?.(null)
	et.setPadding?.(0, top, right, bottom)
}

// Consume the reply/forward (or draft-edit) pre-fill once; null for a blank compose.
const ctx = composeContext.value
composeContext.value = null

// Accounts the user can send as (the From picker). `name` == the sending email.
const accounts = computed(() =>
	(store.user?.accounts ?? []).map((a) => ({
		id: a.id,
		accountName: a.name, // composite id used as the `account` API param
		email: a._name || a.name, // the actual email address
		isPersonal: !!a.is_personal,
	})),
)
// fromAccount holds the composite account name (the `account` API param). If the
// pre-fill carried a from_email, select the matching account; else the active one.
const fromAccount = ref<string>(
	accounts.value.find((a) => a.email === ctx?.from_email)?.accountName ||
		store.account ||
		accounts.value[0]?.accountName ||
		'',
)
const fromName = computed(() => store.user?.full_name ?? '')
const fromEmail = computed(
	() =>
		accounts.value.find((a) => a.accountName === fromAccount.value)?.email ||
		fromAccount.value,
)
const fromLabel = computed(() => fromEmail.value)

const draftId = ref(ctx?.id ?? '')
const inReplyTo = ctx?.in_reply_to ?? ''
const inReplyToId = ctx?.in_reply_to_id ?? ''
const forwardedFromId = ctx?.forwarded_from_id ?? ''

const to = ref<DraftRecipient[]>(ctx?.to ?? [])
const cc = ref<DraftRecipient[]>(ctx?.cc ?? [])
const bcc = ref<DraftRecipient[]>(ctx?.bcc ?? [])
const toPending = ref('')
const ccOpen = ref(false)
const subject = ref(ctx?.subject ?? '')
const body = ref(ctx?.html_body ?? ctx?.quoted_content ?? '')

const sheet = ref<'from' | 'more' | null>(null)
const editor = ref<{ getHtml: () => Promise<string | null> } | null>(null)
const ccVisible = computed(() => ccOpen.value || cc.value.length > 0 || bcc.value.length > 0)

function selectFrom(a: { accountName: string }) {
	fromAccount.value = a.accountName
	sheet.value = null
}

const isRecipientsEmpty = () => !to.value.length && !cc.value.length && !bcc.value.length
const isEmpty = () =>
	isRecipientsEmpty() &&
	!toPending.value.trim() &&
	!subject.value.trim() &&
	!stripHtml(body.value).trim()
const canSend = computed(() => to.value.length > 0 || /\S+@\S+/.test(toPending.value))

function stripHtml(html: string): string {
	return html.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ')
}

function mailPayload(): Record<string, unknown> {
	return {
		account: fromAccount.value,
		from_email: fromEmail.value,
		from_name: fromName.value,
		to: to.value,
		cc: cc.value,
		bcc: bcc.value,
		subject: subject.value,
		html_body: body.value,
		in_reply_to: inReplyTo,
		in_reply_to_id: inReplyToId,
		forwarded_from_id: forwardedFromId,
	}
}

// Snapshot to detect changes worth persisting (mirrors the web isDraftUpdated).
const snapshot = () => JSON.stringify([to.value, cc.value, bcc.value, subject.value, body.value])
let savedSnapshot = snapshot()
let saving = false
let sending = false

async function saveDraft() {
	if (sending || saving || snapshot() === savedSnapshot) return
	if (!draftId.value && isEmpty()) return

	saving = true
	try {
		const res = draftId.value
			? await api.call<{ id: string }>('mail.api.mail.update_draft_mail', {
					id: draftId.value,
					...mailPayload(),
					submit: false,
				})
			: await api.call<{ id: string }>('mail.api.mail.create_mail', {
					...mailPayload(),
					save_as_draft: true,
				})
		if (res?.id) draftId.value = res.id
		savedSnapshot = snapshot()
	} catch {
		// Auto-save is best-effort; surface failures only on explicit send.
	} finally {
		saving = false
	}
}

// The editor's HTML is pulled (not pushed): refresh `body` from the WebView
// right before anything that persists it, so the very last keystrokes are
// included even if the 2s poll hasn't run yet.
async function pullBody() {
	const html = await editor.value?.getHtml()
	if (typeof html === 'string') body.value = html
}

async function send() {
	if (sending) return
	if (isRecipientsEmpty() && !/\S+@\S+/.test(toPending.value)) {
		flash(__('Please add at least one recipient.'))
		return
	}

	await pullBody()
	sending = true
	try {
		if (draftId.value) {
			await api.call('mail.api.mail.update_draft_mail', {
				id: draftId.value,
				...mailPayload(),
				submit: true,
			})
		} else {
			await api.call('mail.api.mail.create_mail', { ...mailPayload(), save_as_draft: false })
		}
		savedSnapshot = snapshot() // sent — nothing left to draft-save on unmount
		$navigateBack()
	} catch (e) {
		sending = false
		flash((e as { message?: string })?.message ?? __('Failed to send.'))
	}
}

// Closing keeps the draft — the unmount autosave persists any changes (skipping
// empty drafts). Discarding is the explicit opt-out via the ⋯ menu.
async function requestClose() {
	await pullBody() // unmount autosave should see the final body
	$navigateBack()
}

// Explicit "Save draft" from the ⋯ menu: persist, then leave.
async function saveAndClose() {
	sheet.value = null
	await pullBody()
	await saveDraft()
	$navigateBack()
}

async function discard() {
	sheet.value = null
	savedSnapshot = snapshot() // prevent the unmount auto-save from re-creating it
	if (draftId.value) {
		try {
			await api.call('mail.api.mail.delete_mail', {
				account: fromAccount.value,
				id: draftId.value,
			})
		} catch {
			// best-effort
		}
	}
	$navigateBack()
}

// Auto-save 2s after the last edit (mirrors the web watchDebounced), and once on leave.
let saveTimer: ReturnType<typeof setTimeout> | null = null
function scheduleSave() {
	if (saveTimer) clearTimeout(saveTimer)
	saveTimer = setTimeout(saveDraft, 2000)
}

const toast = ref<string | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null
function flash(msg: string) {
	toast.value = msg
	if (toastTimer) clearTimeout(toastTimer)
	toastTimer = setTimeout(() => (toast.value = null), 1800)
}

onMounted(() => {
	;[to, cc, bcc, subject, body].forEach((field) => watch(field, scheduleSave, { deep: true }))
})

onUnmounted(() => {
	if (saveTimer) clearTimeout(saveTimer)
	if (toastTimer) clearTimeout(toastTimer)
	saveDraft()
})
</script>
