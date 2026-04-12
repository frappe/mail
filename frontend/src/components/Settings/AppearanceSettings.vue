<template>
	<h1>{{ __('Appearance') }}</h1>
	<FormControl
		:model-value="currentTheme"
		:label="__('Color Scheme')"
		type="select"
		variant="outline"
		:options="COLOR_SCHEMES"
		@update:model-value="setColorScheme"
	/>
	<template v-if="user.data.is_jmap_configured">
		<Switch
			:model-value="showReadingPane"
			:label="__('Show Reading Pane')"
			:description="__('Display message preview beside your mail list')"
			class="!p-0"
			@update:model-value="setReadingPane"
		/>
		<FormControl
			:model-value="groupMessagesBy"
			:label="__('Group Messages By')"
			type="select"
			variant="outline"
			:options="GROUP_MESSAGES_OPTIONS"
			@update:model-value="setGroupBy"
		/>
	</template>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { FormControl, Switch, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import { useLayout, useTheme } from '@/utils/composables'
import type { GroupMessagesBy, Theme } from '@/utils/composables'

const { currentTheme, setTheme } = useTheme()
const { showReadingPane, setShowReadingPane, groupMessagesBy, setGroupMessagesBy } = useLayout()

const user = inject('$user')

type UserSettingsField = 'color_scheme' | 'show_reading_pane' | 'group_messages_by'

const setUserSetting = createResource({
	url: 'frappe.client.set_value',
	makeParams: ({
		fieldname,
		value,
	}: {
		fieldname: UserSettingsField
		value: string | number
	}) => ({
		doctype: 'User Settings',
		name: user.data?.user_settings,
		fieldname,
		value,
	}),
	onError: () => raiseToast(__('Unable to save appearance settings.'), 'error'),
})

const getColorSchemeFromTheme = (theme: Theme): 'System Default' | 'Light Mode' | 'Dark Mode' => {
	if (theme === 'light') return 'Light Mode'
	if (theme === 'dark') return 'Dark Mode'
	return 'System Default'
}

const getUserSettingsGroupBy = (groupBy: GroupMessagesBy): '' | 'Day' | 'Month' => {
	if (groupBy === 'day') return 'Day'
	if (groupBy === 'month') return 'Month'
	return ''
}

const setColorScheme = (theme: Theme) => {
	setTheme(theme)
	if (!user.data?.user_settings) return
	setUserSetting.submit({ fieldname: 'color_scheme', value: getColorSchemeFromTheme(theme) })
}

const setReadingPane = (show: boolean) => {
	setShowReadingPane(show)
	if (!user.data?.user_settings) return
	setUserSetting.submit({ fieldname: 'show_reading_pane', value: show ? 1 : 0 })
}

const setGroupBy = (groupBy: GroupMessagesBy) => {
	setGroupMessagesBy(groupBy)
	if (!user.data?.user_settings) return
	setUserSetting.submit({
		fieldname: 'group_messages_by',
		value: getUserSettingsGroupBy(groupBy),
	})
}

const COLOR_SCHEMES = [
	{ label: __('System Default'), value: 'system' },
	{ label: __('Light Mode'), value: 'light' },
	{ label: __('Dark Mode'), value: 'dark' },
]

const GROUP_MESSAGES_OPTIONS = [
	{ label: __('None'), value: 'none' },
	{ label: __('Day'), value: 'day' },
	{ label: __('Month'), value: 'month' },
]
</script>
