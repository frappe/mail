<template>
	<DashboardLayout
		v-if="addressBook?.doc"
		:breadcrumbs="breadcrumbs"
		:badge-label="addressBook.doc?.default ? __('Default') : ''"
		badge-theme="blue"
	>
		<div class="grid sm:grid-cols-2">
			<div class="space-y-4 rounded-md border p-4">
				<FormControl v-model="addressBook.doc._name" :label="__('Name')" />
				<FormControl
					v-model="addressBook.doc.description"
					type="textarea"
					:label="__('Description')"
				/>
			</div>
		</div>
	</DashboardLayout>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import { FormControl, createDocumentResource } from 'frappe-ui'

import DashboardLayout from '@/components/DashboardLayout.vue'

const { addressBookName } = defineProps<{ addressBookName: string }>()

const user = inject('$user')
const router = useRouter()

const addressBook = createDocumentResource({
	doctype: 'Address Book',
	name: `${user.data.name}|${addressBookName}`,
	onError: () => router.replace({ name: 'AddressBooks' }),
})

const breadcrumbs = computed(() => [
	{ label: __('Address Books'), route: '/address-books' },
	{ label: addressBook.doc?._name || addressBookName },
])
</script>
