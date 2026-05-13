<template>
	<h1>{{ __('Block List') }}</h1>

	<div class="flex gap-4">
		<FormControl
			v-model="email"
			type="text"
			variant="outline"
			:placeholder="__('Enter email address')"
			class="flex-1"
			@keydown.enter="blockEmailAddress.submit()"
		/>
		<Button
			:label="__('Block')"
			variant="solid"
			:loading="blockEmailAddress.loading"
			:disabled="!isEmail(email) || blockedAddresses.data.includes(email)"
			@click="blockEmailAddress.submit()"
		/>
	</div>

	<ListView
		v-if="blockedAddresses.data.length"
		ref="listView"
		:columns="COLUMNS"
		:rows="rows"
		row-key="name"
	>
		<ListHeader />
		<ListRows />
		<ListSelectBanner>
			<template #actions>
				<Button variant="ghost" :label="__('Unblock')" @click="showUnblockModal = true" />
			</template>
		</ListSelectBanner>
	</ListView>
	<div v-else class="text-ink-gray-6 flex flex-col space-y-2 text-sm">
		<p class="text-base font-medium">{{ __('No blocked email addresses.') }}</p>
		<p>{{ MESSAGE }}</p>
	</div>

	<Dialog v-model="showUnblockModal" :options="unblockModalOptions" />
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

const store = userStore()
const { blockedAddresses } = store

const email = ref('')
const listViewRef = useTemplateRef('listView')
const showUnblockModal = ref(false)

const rows = computed(() => blockedAddresses.data.map((address: string) => ({ name: address })))

const blockEmailAddress = createResource({
	url: 'mail.api.mail.block_email_address',
	makeParams: () => ({ account: store.account, email: email.value }),
	onSuccess: () => {
		raiseToast(__('Email address blocked.'))
		email.value = ''
		blockedAddresses.reload()
	},
})

const unblockEmailAddresses = createResource({
	url: 'mail.api.mail.unblock_email_addresses',
	makeParams: () => ({
		account: store.account,
		emails: Array.from(listViewRef.value?.selections),
	}),
	onSuccess: () => {
		raiseToast(__('Email addresses unblocked.'))
		showUnblockModal.value = false
		listViewRef.value?.toggleAllRows()
		blockedAddresses.reload()
	},
})

const unblockModalOptions = computed(() => ({
	title: __('Unblock Email Addresses'),
	message: __('Are you sure you want to unblock the selected email addresses?'),
	actions: [
		{
			label: __('Confirm'),
			variant: 'solid',
			onClick: () => unblockEmailAddresses.submit(),
			loading: unblockEmailAddresses.loading,
		},
	],
}))

const COLUMNS = [{ label: __('Email Address'), key: 'name' }]

const MESSAGE = __(
	'Block specific addresses to prevent their messages from appearing in your inbox.',
)
</script>
