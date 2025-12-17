<template>
	<Dialog v-model="show" :options="options">
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="addressBook"
					type="combobox"
					:label="__('Contact')"
					:options="addressBooks.data.map((ab) => ({ label: ab._name, value: ab.name }))"
					:open-on-click="true"
				/>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Dialog, FormControl } from 'frappe-ui'

import { userStore } from '@/stores/user'

const show = defineModel<boolean>()

const emit = defineEmits(['add'])

const { addressBooks } = userStore()

const addressBook = ref('')

const options = computed(() => ({
	title: __('Add Contacts'),
	actions: [
		{
			label: __('Add'),
			variant: 'solid',
			disabled: !addressBook.value,
			onClick: () => {
				emit('add', {
					address_book: addressBook.value,
					address_book_name:
						addressBooks.data.find((ab) => ab.name === addressBook.value)?._name || '',
				})
				show.value = false
			},
		},
	],
}))

watch(show, (val) => {
	if (val) addressBook.value = ''
})
</script>
