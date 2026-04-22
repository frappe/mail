<template>
	<!-- todo: mobile responsive -->
	<DashboardLayout
		:breadcrumbs="[{ label: __('Address Books') }]"
		:button-label="__('Add Address Book')"
		:button-action="() => (showAddAddressBook = true)"
	>
		<FormControl v-model="search" :placeholder="__('Search')" class="sm:w-80">
			<template #prefix>
				<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
			</template>
		</FormControl>

		<ListView
			v-if="addressBooks?.data"
			ref="listView"
			class="flex-1"
			:columns="LIST_COLUMNS"
			:rows="addressBooks.data"
			:options="LIST_OPTIONS"
			row-key="id"
		>
			<ListHeader />
			<ListRows>
				<template v-if="searchedAddressBooks.length">
					<ListRow
						v-for="row in searchedAddressBooks"
						:key="row.id"
						v-slot="{ column, item }"
						:row="row"
					>
						<Badge
							v-if="column.key === 'default' && item === 1"
							theme="blue"
							:label="__('Default')"
						/>
					</ListRow>
				</template>
				<ListEmptyState v-else />
			</ListRows>
		</ListView>
	</DashboardLayout>

	<AddAddressBookModal v-model="showAddAddressBook" />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
	Badge,
	FeatherIcon,
	FormControl,
	ListEmptyState,
	ListHeader,
	ListRow,
	ListRows,
	ListView,
	usePageMeta,
} from 'frappe-ui'

import { userStore } from '@/stores/user'
import DashboardLayout from '@/components/DashboardLayout.vue'
import AddAddressBookModal from '@/components/Modals/AddAddressBookModal.vue'

usePageMeta(() => ({ title: __('Address Books') }))

const { addressBooks } = userStore()

const showAddAddressBook = ref(false)
const search = ref('')

const searchedAddressBooks = computed(() =>
	addressBooks.data?.filter((ab) => ab._name.toLowerCase().includes(search.value.toLowerCase())),
)

const LIST_COLUMNS = [
	{ label: __('Name'), key: '_name' },
	{ label: '', key: 'default' },
]

const LIST_OPTIONS = {
	selectable: false,
	showTooltip: false,
	emptyState: { description: __('No address books found.') },
	getRowRoute: (row) => ({ name: 'AddressBook', params: { addressBookName: row.id } }),
}
</script>
