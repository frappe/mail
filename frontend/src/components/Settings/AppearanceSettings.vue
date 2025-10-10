<template>
	<h1>{{ __('Appearance') }}</h1>
	<FormControl
		:model-value="currentTheme"
		:label="__('Color Scheme')"
		type="select"
		variant="outline"
		:options="COLOR_SCHEMES"
		@update:model-value="setTheme($event)"
	/>
	<Switch
		:model-value="userLayout === 'split'"
		:label="__('Show Reading Pane')"
		:description="__('Display message preview beside your mail list')"
		@update:model-value="setUserLayout($event ? 'split' : 'full')"
	/>
</template>

<script setup lang="ts">
import { inject, ref } from 'vue'
import { FormControl, Switch } from 'frappe-ui'

import { useTheme } from '@/utils/composables'

import type { LayoutType } from '@/types'

const user = inject('$user')

const userLayout = ref<LayoutType>(
	(localStorage.getItem(`user:${user.data.name}:layout`) as LayoutType) || 'split',
)

const setUserLayout = (type: LayoutType) => {
	localStorage.setItem(`user:${user.data.name}:layout`, type)
	userLayout.value = type
}

const { currentTheme, setTheme } = useTheme()

const COLOR_SCHEMES = [
	{ label: __('Light Mode'), value: 'light' },
	{ label: __('Dark Mode'), value: 'dark' },
	{ label: __('System Default'), value: 'system' },
]
</script>
