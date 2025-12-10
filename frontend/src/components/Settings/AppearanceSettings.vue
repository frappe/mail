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
	<template v-if="user.data.is_mail_user">
		<Switch
			:model-value="showReadingPane"
			:label="__('Show Reading Pane')"
			:description="__('Display message preview beside your mail list')"
			class="!p-0"
			@update:model-value="setShowReadingPane(user.data.name, $event)"
		/>
		<FormControl
			:model-value="groupMessagesBy"
			:label="__('Group Messages By')"
			type="select"
			variant="outline"
			:options="GROUP_MESSAGES_OPTIONS"
			@update:model-value="setGroupMessagesBy(user.data.name, $event)"
		/>
	</template>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { FormControl, Switch } from 'frappe-ui'

import { useLayout, useTheme } from '@/utils/composables'

const { currentTheme, setTheme } = useTheme()
const { showReadingPane, setShowReadingPane, groupMessagesBy, setGroupMessagesBy } = useLayout()

const user = inject('$user')

const COLOR_SCHEMES = [
	{ label: __('Light Mode'), value: 'light' },
	{ label: __('Dark Mode'), value: 'dark' },
	{ label: __('System Default'), value: 'system' },
]

const GROUP_MESSAGES_OPTIONS = [
	{ label: __('None'), value: 'none' },
	{ label: __('Day'), value: 'day' },
	{ label: __('Month'), value: 'month' },
]
</script>
