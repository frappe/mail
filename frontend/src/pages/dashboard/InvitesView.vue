<template>
	<div class="flex items-center space-x-3">
		<FormControl v-model="search" :placeholder="__('Search')" class="w-80">
			<template #prefix>
				<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
			</template>
		</FormControl>
		<FormControl
			v-model="status"
			:placeholder="__('Invitation Status')"
			class="w-40"
			type="select"
			:options="STATUS_OPTIONS"
		/>
	</div>

	<ListView
		v-if="inviteRows"
		ref="listView"
		class="flex-1"
		:columns="LIST_COLUMNS"
		:rows="inviteRows"
		:options="LIST_OPTIONS"
		row-key="name"
	>
		<ListHeader />
		<ListRows>
			<template v-if="inviteRows.length">
				<ListRow
					v-for="row in inviteRows"
					:key="row.name"
					v-slot="{ column, item }"
					:row="row"
					class="hover:!bg-surface-gray-1"
				>
					<ListRowItem :item="item">
						<template v-if="column.key === 'role'">
							<Badge
								:label="row.is_admin ? __('Admin') : __('User')"
								:theme="row.is_admin ? 'orange' : 'blue'"
							/>
						</template>
						<Badge
							v-else-if="column.key === 'status'"
							:label="item"
							:theme="getTheme(item as InviteStatusLabel)"
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
import { computed, ref, useTemplateRef, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
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
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import EditInviteModal from '@/components/Modals/EditInviteModal.vue'

type InviteStatus = 'All' | 'Pending' | 'Accepted' | 'Expired'
type InviteStatusLabel = Exclude<InviteStatus, 'All'>
type InviteRow = {
	name: string
	account: string
	is_admin: boolean
	backup_email: string
	invited_by: string
	is_verified: number | boolean
	status: InviteStatusLabel
}

const search = ref('')
const status = ref<InviteStatus>('All')
const selectedInvite = ref('')
const showEditInvite = ref(false)
const showDeleteInvites = ref(false)

const invites = createResource({
	url: 'mail.api.admin.get_invites',
	makeParams: () => ({
		search: search.value,
		...(status.value !== 'All' ? { status: status.value } : {}),
	}),
	auto: true,
	cache: ['memberInvites', search.value, status.value],
})

const inviteRows = computed<InviteRow[]>(() =>
	((invites.data || []) as Omit<InviteRow, 'status'>[]).map((row) => ({
		...row,
		is_admin: Boolean(row.is_admin),
		status: status.value !== 'All' ? status.value : row.is_verified ? 'Accepted' : 'Pending',
	})),
)

watchDebounced(() => search.value, invites.reload, { debounce: 300 })
watch(() => status.value, invites.reload)

const reloadInvites = () => invites.reload()
defineExpose({ reloadInvites })

const listView = useTemplateRef<{
	selections?: Set<string>
	toggleAllRows?: () => void
}>('listView')

const deleteInvites = createResource({
	url: 'mail.api.admin.delete_account_requests',
	makeParams: () => ({ names: Array.from(listView.value?.selections || []) }),
	onSuccess: () => {
		invites.reload()
		showDeleteInvites.value = false
		raiseToast(__('Invites deleted.'))
		listView.value?.toggleAllRows?.()
	},
	onError: (error: { messages?: string[] }) => {
		showDeleteInvites.value = false
		raiseToast(error.messages?.[0] || __('Failed to delete invites.'), 'error')
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
	{ label: __('Role'), key: 'role' },
	{ label: __('Backup Email'), key: 'backup_email' },
	{ label: __('Invited By'), key: 'invited_by' },
	{ label: __('Invitation Status'), key: 'status' },
]

const LIST_OPTIONS = {
	showTooltip: false,
	rowHeight: 50,
	emptyState: { description: __('No invites found.') },
	onRowClick: (row: InviteRow) => {
		selectedInvite.value = row.name
		showEditInvite.value = true
	},
}

const STATUS_OPTIONS = [
	{ label: __('All'), value: 'All' },
	{ label: __('Pending'), value: 'Pending' },
	{ label: __('Accepted'), value: 'Accepted' },
	{ label: __('Expired'), value: 'Expired' },
]

const getTheme = (status: InviteStatusLabel) =>
	status === 'Accepted' ? 'green' : status === 'Expired' ? 'gray' : 'orange'
</script>
