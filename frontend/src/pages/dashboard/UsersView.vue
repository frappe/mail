<template>
	<div class="flex items-center space-x-3">
		<FormControl v-model="search" :placeholder="__('Search')" class="w-80">
			<template #prefix>
				<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
			</template>
		</FormControl>
	</div>
	<ListView
		v-if="members?.data"
		ref="listView"
		class="flex-1"
		:columns="LIST_COLUMNS"
		:rows="members.data"
		:options="LIST_OPTIONS"
		row-key="name"
	>
		<ListHeader />
		<ListRows>
			<template v-if="members.data.length">
				<ListRow
					v-for="row in members.data"
					:key="row.name"
					v-slot="{ column, item }"
					:row="row"
					class="hover:bg-surface-gray-1 cursor-pointer rounded"
				>
					<ListRowItem :item="item">
						<template v-if="column.key === 'user'">
							<div class="flex items-center space-x-2">
								<Avatar :image="row.user_image" :label="row.full_name" size="lg" />
								<div class="text-sm">
									<p class="font-medium">{{ row.full_name }}</p>
									<p class="text-ink-gray-5 mt-0.5">{{ row.name }}</p>
								</div>
							</div>
						</template>
						<template v-else-if="column.key === 'roles'">
							<div class="flex flex-wrap gap-1">
								<Badge
									v-for="role in row.assigned_roles"
									:key="role"
									:label="role"
									:theme="
										role === 'admin'
											? 'red'
											: role === 'tenant-admin'
												? 'orange'
												: role === 'user'
													? 'blue'
													: 'gray'
									"
								/>
							</div>
						</template>
						<template v-else-if="column.key === 'quota'">
							<div class="flex items-center space-x-2">
								<div class="bg-surface-gray-4 h-1.5 w-16 rounded-full">
									<div
										class="h-1.5 rounded-full"
										:class="
											row.quota_usage_percent > 80
												? 'bg-surface-red-6'
												: 'bg-surface-gray-7'
										"
										:style="{
											width: `${row.quota_usage_percent || 0}%`,
											maxWidth: '100%',
										}"
									/>
								</div>
								<span class="text-ink-gray-5 text-sm">
									{{ row.quota_usage_percent }}%
								</span>
							</div>
						</template>
						<template v-else-if="column.key === 'last_active'">
							<span class="text-ink-gray-5 text-sm">
								{{
									row.last_active
										? dayjs(row.last_active).fromNow()
										: __('Never')
								}}
							</span>
						</template>
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
					@click="showDeleteMembers = true"
				/>
			</template>
		</ListSelectBanner>
	</ListView>
	<Dialog v-model="showDeleteMembers" :options="DELETE_MEMBERS_OPTIONS" />
</template>

<script setup lang="ts">
import { inject, ref, useTemplateRef } from 'vue'
import { watchDebounced } from '@vueuse/core'
import {
	Avatar,
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

const dayjs = inject('$dayjs')

const search = ref('')
const showDeleteMembers = ref(false)
const listView = useTemplateRef('listView')

const members = createResource({
	url: 'mail.api.admin.get_members',
	makeParams: () => ({
		search: search.value,
	}),
	auto: true,
	cache: ['mailMembers', search.value],
})

watchDebounced(() => search.value, members.reload, { debounce: 300 })

const reloadMembers = () => members.reload()
defineExpose({ reloadMembers })

const LIST_COLUMNS = [
	{ label: __('User'), key: 'user' },
	{ label: __('Roles'), key: 'roles' },
	{ label: __('Emails'), key: 'email_count' },
	{ label: __('Groups'), key: 'group_count' },
	{ label: __('Lists'), key: 'list_count' },
	{ label: __('Quota'), key: 'quota' },
	{ label: __('Last Active'), key: 'last_active' },
]

const LIST_OPTIONS = {
	showTooltip: false,
	rowHeight: 50,
	emptyState: { description: __('No members found.') },
	getRowRoute: (row) => ({ name: 'Member', params: { memberName: row.name } }),
}

const deleteMembers = createResource({
	url: 'mail.api.admin.delete_members',
	makeParams: () => ({ names: Array.from(listView.value?.selections) }),
	onSuccess: () => {
		members.reload()
		showDeleteMembers.value = false
		raiseToast(__('Members deleted.'))
		listView.value?.toggleAllRows()
	},
	onError: (error) => {
		showDeleteMembers.value = false
		raiseToast(error.messages[0], 'error')
	},
})

const DELETE_MEMBERS_OPTIONS = {
	title: __('Delete Members'),
	message: __(
		'Are you sure you want to delete the selected members? This action cannot be undone.',
	),
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: deleteMembers.submit }],
}
</script>
