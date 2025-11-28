<template>
	<div class="flex items-center space-x-3">
		<FormControl v-model="search" :placeholder="__('Search')" class="w-80">
			<template #prefix>
				<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
			</template>
		</FormControl>
		<FormControl
			v-model="role"
			:placeholder="__('Assigned Role')"
			class="w-40"
			type="select"
			:options="ROLE_OPTIONS"
		/>
		<FormControl
			v-model="status"
			:placeholder="__('Invitation Status')"
			class="w-40"
			type="select"
			:options="STATUS_OPTIONS"
		/>
	</div>

	<ListView
		v-if="invites?.data"
		ref="listView"
		class="flex-1"
		:columns="LIST_COLUMNS"
		:rows="invites.data"
		:options="LIST_OPTIONS"
		row-key="name"
	>
		<ListHeader />
		<ListRows>
			<template v-if="invites.data.length">
				<ListRow
					v-for="row in invites.data"
					:key="row.name"
					v-slot="{ column, item }"
					:row="row"
					class="hover:!bg-surface-gray-1"
				>
					<ListRowItem :item="item">
						<Badge
							v-if="column.key == 'is_admin'"
							:label="__(item ? 'Mail Admin' : 'Mail User')"
							:theme="item ? 'blue' : 'gray'"
						/>
						<Badge
							v-else-if="column.key == 'status'"
							:label="item"
							:theme="getTheme(item)"
						/>
					</ListRowItem>
				</ListRow>
			</template>
			<ListEmptyState v-else />
		</ListRows>
		<ListSelectBanner>
			<template #actions>
				<Button
					variant="ghost"
					theme="red"
					:label="__('Delete')"
					@click="showDeleteInvites = true"
				/>
			</template>
		</ListSelectBanner>
	</ListView>

	<EditInviteModal
		v-if="selectedInvite"
		v-model="showEditInvite"
		:invite-i-d="selectedInvite"
		@reload-invites="invites.reload()"
	/>
	<Dialog v-model="showDeleteInvites" :options="DELETE_INVITES_OPTIONS" />
</template>

<script setup lang="ts">
import { inject, ref, useTemplateRef } from 'vue'
import { useDebounce } from '@vueuse/core'
import {
	Badge,
	Button,
	Dialog,
	FeatherIcon,
	FormControl,
	ListEmptyState,
	ListHeader,
	ListRow,
	ListRowItem,
	ListRows,
	ListSelectBanner,
	ListView,
	createResource,
	useList,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import EditInviteModal from '@/components/Modals/EditInviteModal.vue'

const dayjs = inject('$dayjs')
const user = inject('$user')

const search = ref('')
const debouncedSearch = useDebounce(search, 500)
const role = ref<'Mail User' | 'Mail Admin' | ''>('')
const status = ref<'Pending' | 'Accepted' | 'Expired' | ''>('')
const selectedInvite = ref('')
const showEditInvite = ref(false)
const showDeleteInvites = ref(false)

const invites = useList({
	doctype: 'Mail Account Request',
	fields: ['name', 'email', 'account', 'is_admin', 'is_verified', 'expires_at', 'invited_by'],
	orderBy: 'creation desc',
	filters: () => {
		const filters: Record<string, string | string[] | number> = {
			tenant: user.data?.tenant,
			is_invite: 1,
			send_invite: 1,
			account: ['like', debouncedSearch.value],
		}

		if (role.value) filters.is_admin = Number(role.value === 'Mail Admin')
		if (status.value) {
			if (status.value === 'Accepted') filters.is_verified = 1
			else {
				filters.is_verified = 0
				filters.expires_at = [status.value === 'Pending' ? '>=' : '<=', dayjs()]
			}
		}

		return filters
	},
	transform: (data) =>
		data.map((row) => ({
			...row,
			status: row.is_verified
				? 'Accepted'
				: dayjs().isAfter(row.expires_at)
					? 'Expired'
					: 'Pending',
		})),
	limit: 100,
	cacheKey: [
		'memberInvites',
		user.data?.tenant,
		debouncedSearch.value,
		role.value,
		status.value,
	],
})

const reloadInvites = () => invites.reload()
defineExpose({ reloadInvites })

const listView = useTemplateRef('listView')

const deleteInvites = createResource({
	url: 'mail.api.admin.delete_account_requests',
	makeParams: () => ({ names: Array.from(listView.value?.selections) }),
	onSuccess: () => {
		invites.reload()
		showDeleteInvites.value = false
		raiseToast(__('Invites deleted successfully.'))
		listView.value?.toggleAllRows()
	},
	onError: (error) => {
		showDeleteInvites.value = false
		raiseToast(error.messages[0], 'error')
	},
})

const DELETE_INVITES_OPTIONS = {
	title: __('Delete Invites'),
	message: __(
		'Are you sure you want to delete the selected invites? This will invalidate them for the recipients if pending.',
	),
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: deleteInvites.submit }],
}

const LIST_COLUMNS = [
	{ label: __('Assigned Email'), key: 'account' },
	{ label: __('Assigned Role'), key: 'is_admin' },
	{ label: __('Backup Email'), key: 'email' },
	{ label: __('Invited By'), key: 'invited_by' },
	{ label: __('Invitation Status'), key: 'status' },
]

const LIST_OPTIONS = {
	showTooltip: false,
	rowHeight: 50,
	emptyState: { description: __('No invites found.') },
	onRowClick: (row) => {
		selectedInvite.value = row.name
		showEditInvite.value = true
	},
}

const ROLE_OPTIONS = [
	{ label: '', value: '' },
	{ label: __('Mail User'), value: 'Mail User' },
	{ label: __('Mail Admin'), value: 'Mail Admin' },
]

const STATUS_OPTIONS = [
	{ label: '', value: '' },
	{ label: __('Pending'), value: 'Pending' },
	{ label: __('Accepted'), value: 'Accepted' },
	{ label: __('Expired'), value: 'Expired' },
]

const getTheme = (status: 'Accepted' | 'Expired' | 'Pending') =>
	status === 'Accepted' ? 'green' : status === 'Expired' ? 'gray' : 'orange'
</script>
