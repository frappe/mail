<template>
	<Dialog v-model="show" :options>
		<template #body-content>
			<div class="flex items-center space-x-4">
				<FormControl
					v-model="contact"
					type="combobox"
					:options="
						contacts?.data
							.filter((c) => !selectedContacts.map((sc) => sc.id).includes(c.id))
							.map((c) => ({ label: c.full_name, value: c.id }))
					"
					:open-on-click="true"
					class="w-full"
					@input="search = $event"
				/>
				<Button
					:label="__('Add')"
					:disabled="!contact"
					@click="
						() => {
							selectedContacts.push(contacts.data.find((c) => c.id === contact))
							contact = ''
						}
					"
				/>
			</div>
			<div class="max-h-96 overflow-auto">
				<div
					v-for="c in selectedContacts"
					:key="c.id"
					class="flex items-center justify-between pt-4"
				>
					<div class="space-y-1">
						<div class="text-base font-medium">{{ c.full_name }}</div>
						<div class="text-ink-gray-5 text-sm">{{ c.kind }}</div>
					</div>
					<Button
						icon="x"
						@click="selectedContacts = selectedContacts.filter((sc) => sc.id !== c.id)"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { Button, Dialog, FormControl, createResource } from 'frappe-ui'

const show = defineModel<boolean>()

const emit = defineEmits(['add'])

const user = inject('$user')

const search = ref('')
const contact = ref('')
const selectedContacts = ref([])

const contacts = createResource({
	url: 'mail.api.contacts.get_contact_cards',
	auto: true,
	makeParams: () => ({ filter: { text: search.value } }),
	cache: ['contacts', user.data.name, search.value, 50],
})

watchDebounced(() => search.value, contacts.reload, { debounce: 300 })

const options = computed(() => ({
	title: __('Add Contacts'),
	actions: [
		{
			label: __('Save'),
			variant: 'solid',
			disabled: selectedContacts.value.length === 0,
			onClick: () => {
				emit('add', selectedContacts.value)
				show.value = false
			},
		},
	],
}))

watch(show, (val) => {
	if (!val) return

	search.value = ''
	contact.value = ''
	selectedContacts.value = []
})
</script>
