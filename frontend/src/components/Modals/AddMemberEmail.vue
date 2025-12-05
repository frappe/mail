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

const show = defineModel<boolean>()

const { isList } = defineProps<{ isList: boolean }>()

const emit = defineEmits(['addEmail'])

const user = inject('$user')

const email = ref('')
const domain = ref('')

const domains = createResource({
	url: 'mail.api.admin.get_domains',
	auto: true,
	makeParams: () => ({ tenant: user.data.tenant, is_verified: 1 }),
	transform: (data) => data.map((domain) => domain.name),
	cache: ['mailTenantDomains', user.data.tenant, '', 'Verified'],
})

watch(show, (val) => {
	if (val) email.value = ''
})
</script>
