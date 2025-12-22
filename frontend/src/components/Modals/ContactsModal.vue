<template>
	<Dialog v-model="show" :options="options">
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="selectFrom"
					:label="__('Select From')"
					type="combobox"
					:open-on-click="true"
					:options="selectFromOptions"
					@update:model-value="contacts.reload"
				/>
				<hr />
				<FormControl v-model="search" :placeholder="__('Search...')" />
				<ListView
					v-if="contacts?.data"
					ref="listView"
					class="h-60 shrink-0"
					:columns="LIST_COLUMNS"
					:rows="contacts.data"
					:options="LIST_OPTIONS"
					row-key="email"
				>
					<ListHeader />
					<ListRows v-if="contacts.data.length" @scroll="loadMoreContacts" />
					<ListEmptyState v-else />
				</ListView>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, useTemplateRef } from 'vue'
import { useDebounceFn, watchDebounced } from '@vueuse/core'
import {
	Dialog,
	FormControl,
	ListEmptyState,
	ListHeader,
	ListRows,
	ListView,
	createResource,
} from 'frappe-ui'

import { userStore } from '@/stores/user'

const show = defineModel<boolean>()

const emit = defineEmits(['insert'])

const { addressBooks } = userStore()

const listView = useTemplateRef('listView')

const options = computed(() => ({
	title: __('Select Contacts'),
	actions: [
		{
			label: __('Insert'),
			variant: 'solid',
			disabled: listView.value?.selections.size === 0,
			onClick: () => {
				emit('insert', Array.from(listView.value?.selections))
				show.value = false
			},
		},
	],
}))

const selectFrom = ref('all')
const selectFromOptions = computed(() => [
	{ label: __('All Contacts'), value: 'all' },
	...addressBooks.data.map((ab) => ({
		label: ab._name,
		value: ab.id,
	})),
])

const search = ref('')
const limit = ref(50)

const contacts = createResource({
	url: 'mail.api.contacts.get_contacts',
	auto: true,
	makeParams: () => {
		const filters = []

		if (search.value)
			filters.push({
				operator: 'OR',
				conditions: [{ text: search.value }, { email: search.value }],
			})

		if (selectFrom.value !== 'all') filters.push({ inAddressBook: selectFrom.value })

		const filter =
			filters.length === 0
				? null
				: filters.length === 1
					? filters[0]
					: { operator: 'AND', conditions: filters }

		return { filter, limit: limit.value }
	},
})

watchDebounced(() => search.value, contacts.reload, { debounce: 300 })

const loadMoreContacts = useDebounceFn((e) => {
	const { scrollTop, scrollHeight, clientHeight } = e.target
	if (scrollTop + clientHeight >= scrollHeight - 10 && contacts.data?.length === limit.value) {
		limit.value += 50
		contacts.reload()
		setTimeout(
			() => e.target.scrollTo({ top: e.target.scrollHeight, behavior: 'smooth' }),
			100,
		)
	}
}, 500)

const LIST_COLUMNS = [
	{ label: __('Name'), key: 'full_name' },
	{ label: __('Email'), key: 'email' },
]

const LIST_OPTIONS = { showTooltip: false, emptyState: { description: __('No contacts.') } }
</script>
