<template>
	<Dialog
		v-model="show"
		:options="{
			title: isList ? __('New Mailing List') : __('New Email Address'),
			actions: [
				{
					label: __('Add'),
					variant: 'solid',
					disabled: isList ? !list : !(email && domain),
					onClick: () => {
						emit('addEmail', isList ? list : `${email}@${domain}`)
						show = false
					},
				},
			],
		}"
	>
		<template #body-content>
			<FormControl
				v-if="isList"
				v-model="list"
				type="combobox"
				:label="__('Mailing List')"
				placeholder="team@yourdomain.com"
				class="w-full"
				:options="lists.data"
				:open-on-click="true"
			/>

			<div v-else class="flex items-center justify-between">
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
import { inject, ref, watch } from 'vue'
import { Dialog, FeatherIcon, FormControl, createResource } from 'frappe-ui'

import { userStore } from '@/stores/user'

const show = defineModel<boolean>()

const { isList } = defineProps<{ isList: boolean }>()

const emit = defineEmits(['addEmail'])

const user = inject('$user')
const { domains } = userStore()

const email = ref('')
const domain = ref('')
const list = ref('')

const lists = createResource({
	url: 'mail.api.admin.get_mailing_lists',
	auto: true,
	transform: (data) => data.map((l) => l.name),
	cache: ['mailTenantMailingLists', user.data?.tenant],
})

watch(show, (val) => {
	if (!val) return
	email.value = ''
	domain.value = ''
	list.value = ''
})
</script>
