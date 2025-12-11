<template>
	<DashboardLayout :breadcrumbs="BREADCRUMBS">hi</DashboardLayout>
</template>

<script setup lang="ts">
import DashboardLayout from '@/components/DashboardLayout.vue'

const { addressBookName } = defineProps<{ addressBookName: string }>()

const BREADCRUMBS = [
	{ label: __('Address Books'), route: '/address-books' },
	{ label: addressBookName },
]
</script>
