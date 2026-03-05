<template>
	<DashboardLayout
		:breadcrumbs="[{ label: __('Domains') }]"
		:button-label="__('Add Domain')"
		:button-action="() => (showAddDomain = true)"
	>
		<div class="flex items-center space-x-3">
			<FormControl v-model="search" :placeholder="__('Search')" class="w-80">
				<template #prefix>
					<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
				</template>
			</FormControl>
			<FormControl
				v-model="status"
				:placeholder="__('Status')"
				class="w-40"
				type="select"
				:options="STATUS_OPTIONS"
				@update:model-value="domains.reload()"
			/>
		</div>
		<ListView
			v-if="domains?.data"
			class="flex-1"
			:columns="LIST_COLUMNS"
			:rows="domains.data"
			:options="LIST_OPTIONS"
			row-key="name"
		>
			<ListHeader />
			<ListRows>
				<template v-if="domains.data.length">
					<ListRow
						v-for="row in domains.data"
						:key="row.name"
						v-slot="{ column, item }"
						:row="row"
						class="hover:!bg-surface-gray-1"
					>
						<ListRowItem :item="String(item)">
							<Badge
								v-if="column.key === 'is_verified'"
								:theme="item ? 'green' : 'gray'"
								:label="item ? __('Verified') : __('Not Verified')"
							/>
						</ListRowItem>
					</ListRow>
				</template>
				<ListEmptyState v-else />
			</ListRows>
		</ListView>
	</DashboardLayout>
	<AddDomainModal v-model="showAddDomain" @reload-domains="domains.reload()" />
</template>
<script setup lang="ts">
import { inject, ref } from 'vue'
import { watchDebounced } from '@vueuse/core'
import {
	Badge,
	FeatherIcon,
	FormControl,
	ListEmptyState,
	ListHeader,
	ListRow,
	ListRowItem,
	ListRows,
	ListView,
	createResource,
} from 'frappe-ui'

import DashboardLayout from '@/components/DashboardLayout.vue'
import AddDomainModal from '@/components/Modals/AddDomainModal.vue'

const user = inject('$user')

const showAddDomain = ref(false)
const search = ref('')
const status = ref<'Verified' | 'Not Verified' | ''>('')

const domains = createResource({
	url: 'mail.api.admin.get_domains',
	auto: true,
	makeParams: () => ({
		txt: search.value,
		is_verified: status.value === 'Verified' ? 1 : status.value === 'Not Verified' ? 0 : null,
	}),
	cache: ['mailTenantDomains', user.data.tenant, search.value, status.value],
})

watchDebounced(() => search.value, domains.reload, { debounce: 300 })

const LIST_COLUMNS = [
	{ label: __('Domain'), key: 'name' },
	{ label: __('Status'), key: 'is_verified' },
	{ label: __('Addresses'), key: 'total_members' },
]

const LIST_OPTIONS = {
	selectable: false,
	showTooltip: false,
	emptyState: { description: __('No domains found.') },
	getRowRoute: (row) => ({ name: 'Domain', params: { domainName: row.name } }),
}

const STATUS_OPTIONS = [
	{ label: '', value: 'Both' },
	{ label: __('Verified'), value: 'Verified' },
	{ label: __('Not Verified'), value: 'Not Verified' },
]
</script>
