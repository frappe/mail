<template>
	<h1>{{ __('Import') }}</h1>
	<TabButtons v-model="activeType" :buttons="typeButtons" />
	<component :is="activeComponent" :key="activeType" />
</template>

<script setup lang="ts">
import { type Component, computed, markRaw, ref } from 'vue'
import { TabButtons } from 'frappe-ui'

import CalendarImportSettings from '@/components/Settings/CalendarImportSettings.vue'
import MailImportSettings from '@/components/Settings/MailImportSettings.vue'

const activeType = ref('mail')

const typeButtons = [
	{ label: __('Mail'), value: 'mail' },
	{ label: __('Calendar'), value: 'calendar' },
]

const components: Record<string, Component> = {
	mail: markRaw(MailImportSettings),
	calendar: markRaw(CalendarImportSettings),
}

const activeComponent = computed(() => components[activeType.value])
</script>
