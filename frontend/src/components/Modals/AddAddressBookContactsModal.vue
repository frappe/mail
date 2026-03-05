<template>
	<Dialog v-model="show" :options>
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="search" :placeholder="__('Search...')" />
				<ListView
					v-if="contacts?.data"
					ref="listView"
					class="h-60 shrink-0"
					:columns="LIST_COLUMNS"
					:rows="contacts.data"
					:options="LIST_OPTIONS"
					row-key="id"
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

import { extractNameFromEmail } from '@/utils'

const show = defineModel<boolean>()

const emit = defineEmits(['add'])

const listView = useTemplateRef('listView')

const options = computed(() => ({
	title: __('Select Contacts'),
	actions: [
		{
			label: __('Add'),
			variant: 'solid',
			disabled: listView.value?.selections.size === 0,
			onClick: () => {
				emit('add', Array.from(listView.value?.selections))
				show.value = false
			},
		},
	],
}))

const search = ref('')
const limit = ref(50)

const contacts = createResource({
	url: 'mail.api.contacts.get_contact_cards',
	auto: true,
	makeParams: () => ({ filter: { text: search.value }, limit: limit.value }),
	transform: (data) =>
		data.map((c) => {
			const full_name = c.full_name || extractNameFromEmail(c.emails[0]?.address || '')

			let email = ''
			if (c.emails.length === 1) email = c.emails[0].address
			else if (c.emails.length > 1)
				email = __('{0} + {1} more', [c.emails[0].address, c.emails.length - 1])

			return { ...c, full_name, email }
		}),
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

const LIST_OPTIONS = { showTooltip: false, emptyState: { description: __('No contacts to add.') } }
</script>
