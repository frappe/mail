<template>
	<Dialog
		v-model="show"
		:options="{
			title: isList ? __('New Mailing List') : __('New Email Address'),
			actions: [
				{
					label: __('Add'),
					variant: 'solid',
					disabled: !(email && domain),
					onClick: () => {
						emit('addEmail', `${email}@${domain}`)
						show = false
					},
				},
			],
		}"
	>
		<template #body-content>
			<div class="flex items-center justify-between">
				<FormControl
					v-model="email"
					:label="__('Name')"
					:placeholder="isList ? 'list' : 'johndoe'"
					class="w-full"
				/>
				<FeatherIcon
					class="text-ink-gray-3 mx-2.5 mb-1.5 mt-auto h-4 w-4"
					name="at-sign"
				/>
				<FormControl
					v-model="domain"
					type="combobox"
					:label="__('Domain')"
					placeholder="yourdomain.com"
					class="w-full"
					:options="domains.data"
					:open-on-click="true"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, FeatherIcon, FormControl } from 'frappe-ui'

import { userStore } from '@/stores/user'

const show = defineModel<boolean>()

const { isList } = defineProps<{ isList: boolean }>()

const emit = defineEmits(['addEmail'])

const { domains } = userStore()

const email = ref('')
const domain = ref('')

watch(show, (val) => {
	if (val) email.value = ''
})
</script>
