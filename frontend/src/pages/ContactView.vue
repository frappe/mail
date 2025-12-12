<template>
	<DashboardLayout v-if="contact?.doc" :breadcrumbs="breadcrumbs"> hi </DashboardLayout>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import { FormControl, createDocumentResource } from 'frappe-ui'

import DashboardLayout from '@/components/DashboardLayout.vue'

const { contactName } = defineProps<{ contactName: string }>()

const user = inject('$user')
const router = useRouter()

const contact = createDocumentResource({
	doctype: 'Contact Card',
	name: `${user.data.name}|${contactName}`,
	onError: () => router.replace({ name: 'Contacts' }),
})

const breadcrumbs = computed(() => [
	{ label: __('Contacts'), route: '/contacts' },
	{ label: contact.doc?.full_name || contactName },
])
</script>
