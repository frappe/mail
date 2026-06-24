<template>
	<!-- A single h-full flex column gives the ListView a bounded flex parent so it fills the panel and
	scrolls within itself, instead of taking a small intrinsic height with empty space below. -->
	<div class="flex min-h-0 flex-1 flex-col gap-5">
		<h1>{{ __('Screened Senders') }}</h1>

		<div class="flex gap-4">
			<FormControl
				v-model="email"
				type="text"
				variant="outline"
				:placeholder="__('Enter email address')"
				class="flex-1"
				@keydown.enter="screenEmailAddress.submit()"
			/>
			<!-- FormControl forces `w-full` on selects, so constrain it with a fixed-width wrapper
			instead of letting it claim the whole row and squeeze the email input. -->
			<div class="w-36 shrink-0">
				<FormControl
					v-model="action"
					type="select"
					variant="outline"
					:options="ACTION_OPTIONS"
				/>
			</div>
			<Button
				:label="__('Add')"
				variant="solid"
				:loading="screenEmailAddress.loading"
				:disabled="!isEmail(email) || isAlreadyScreened"
				@click="screenEmailAddress.submit()"
			/>
		</div>

		<ListView
			v-if="rows.length"
			ref="listView"
			class="min-h-0 flex-1"
			:columns="COLUMNS"
			:rows="rows"
			row-key="email"
		>
			<ListHeader />
			<ListRows />
			<ListSelectBanner>
				<template #actions>
					<Button
						variant="ghost"
						:label="__('Remove')"
						@click="showRemoveModal = true"
					/>
				</template>
			</ListSelectBanner>
		</ListView>
		<div v-else class="text-ink-gray-6 flex flex-col space-y-2 text-sm">
			<p class="text-base font-medium">{{ __('No screened senders.') }}</p>
			<p>{{ MESSAGE }}</p>
		</div>

		<Dialog v-model="showRemoveModal" :options="removeModalOptions" />
	</div>
</template>

<script setup lang="ts">
import { computed, ref, useTemplateRef } from 'vue'
import {
	Button,
	Dialog,
	FormControl,
	ListHeader,
	ListRows,
	ListSelectBanner,
	ListView,
	createResource,
} from 'frappe-ui'

import { isEmail, raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

import type { ScreenedAddress, ScreeningAction } from '@/types'

const store = userStore()
const { screenedAddresses } = store

const email = ref('')
const action = ref<ScreeningAction>('Reject')
const listViewRef = useTemplateRef('listView')
const showRemoveModal = ref(false)

// 'Reject' discards the sender's future mail silently; 'Spam' files it into the Spam folder.
const ACTION_OPTIONS = [
	{ label: __('Block'), value: 'Reject' },
	{ label: __('Move to Junk'), value: 'Spam' },
]
const ACTION_LABELS: Partial<Record<ScreeningAction, string>> = {
	Reject: __('Block'),
	Spam: __('Move to Junk'),
}

const isAlreadyScreened = computed(() =>
	(screenedAddresses.data ?? []).some((a: ScreenedAddress) => a.email === email.value),
)

const rows = computed(() =>
	(screenedAddresses.data ?? []).map((a: ScreenedAddress) => ({
		email: a.email,
		action: ACTION_LABELS[a.action] ?? a.action,
	})),
)

const screenEmailAddress = createResource({
	url: 'mail.api.mail.screen_email_address',
	makeParams: () => ({ account_id: store.accountId, email: email.value, action: action.value }),
	onSuccess: () => {
		raiseToast(__('Sender screened.'))
		email.value = ''
		screenedAddresses.reload()
	},
})

const unscreenEmailAddresses = createResource({
	url: 'mail.api.mail.unscreen_email_addresses',
	makeParams: () => ({
		account_id: store.accountId,
		emails: Array.from(listViewRef.value?.selections),
	}),
	onSuccess: () => {
		raiseToast(__('Senders removed.'))
		showRemoveModal.value = false
		listViewRef.value?.toggleAllRows()
		screenedAddresses.reload()
	},
})

const removeModalOptions = computed(() => ({
	title: __('Remove Screened Senders'),
	message: __('Are you sure you want to remove the selected senders from your screened list?'),
	actions: [
		{
			label: __('Confirm'),
			variant: 'solid',
			onClick: () => unscreenEmailAddresses.submit(),
			loading: unscreenEmailAddresses.loading,
		},
	],
}))

// `fr` units (numbers) so the columns share the row width instead of overflowing (percentages plus the
// checkbox column would exceed 100% and add a horizontal scrollbar).
const COLUMNS = [
	{ label: __('Email Address'), key: 'email', width: 4 },
	{ label: __('Action'), key: 'action', width: 1 },
]

const MESSAGE = __(
	'Screen specific senders to either reject their messages or send them straight to Spam.',
)
</script>
