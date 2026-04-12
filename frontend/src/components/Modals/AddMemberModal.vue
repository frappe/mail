<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Add Member'),
			actions: [
				{
					label: __(accountRequest.send_invite ? 'Invite Member' : 'Add Member'),
					variant: 'solid',
					onClick: addMember.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<div class="flex items-center justify-between">
					<FormControl
						v-model="accountRequest.username"
						:label="__('Username')"
						placeholder="johndoe"
						class="w-full"
					/>
					<FeatherIcon
						class="text-ink-gray-3 mx-2.5 mb-1.5 mt-auto h-4 w-4"
						name="at-sign"
					/>
					<FormControl
						v-model="accountRequest.domain"
						type="combobox"
						:label="__('Domain')"
						placeholder="yourdomain.com"
						class="w-full"
						:options="domains.data"
						:open-on-click="true"
					/>
				</div>
				<div class="space-y-1.5">
					<label class="text-ink-gray-5 block text-xs">{{ __('Roles') }}</label>
					<MultiSelect v-model="accountRequest.roles" :options="ROLE_OPTIONS" />
				</div>
				<FormControl
					v-model="accountRequest.backup_email"
					type="email"
					:label="__('Backup Email')"
					placeholder="johndoe@personal.com"
				/>
				<hr />

				<Switch
					v-model="accountRequest.send_invite"
					:label="__('Send Invite')"
					class="hover:!bg-surface-white !cursor-default !p-0"
				/>
				<FormControl
					v-if="accountRequest.send_invite"
					v-model="accountRequest.expires_at"
					:label="__('Expires At')"
					type="datetime-local"
				/>
				<template v-else>
					<FormControl
						v-model="accountRequest.first_name"
						:label="__('First Name')"
						placeholder="John"
					/>
					<FormControl
						v-model="accountRequest.last_name"
						:label="__('Last Name')"
						placeholder="Doe"
					/>
					<FormControl
						v-model="accountRequest.password"
						type="password"
						:label="__('Password')"
						placeholder="••••••••"
					/>
				</template>
				<ErrorMessage :message="addMember.error?.messages[0]" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { inject, reactive, watch } from 'vue'
import {
	Dialog,
	ErrorMessage,
	FeatherIcon,
	FormControl,
	MultiSelect,
	Switch,
	createResource,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

const show = defineModel<boolean>()

const dayjs = inject('$dayjs')

const { domains } = userStore()

const ROLE_OPTIONS = [
	{ label: __('User'), value: 'User' },
	{ label: __('Admin'), value: 'Admin' },
	{ label: __('Tenant Admin'), value: 'Tenant Admin' },
]

const defaultAccountRequest = {
	username: '',
	domain: '',
	roles: ['User'] as string[],
	send_invite: true,
	expires_at: dayjs().add(1, 'day').format('YYYY-MM-DDTHH:mm'),
	backup_email: '',
	first_name: '',
	last_name: '',
	password: '',
}

const accountRequest = reactive({ ...defaultAccountRequest })

const emit = defineEmits(['reload'])

watch(
	() => accountRequest.send_invite,
	() => addMember.reset(),
)
watch(show, () => {
	if (show.value) {
		Object.assign(accountRequest, {
			...defaultAccountRequest,
			roles: [...defaultAccountRequest.roles],
		})
		addMember.reset()
	}
})

const addMember = createResource({
	url: 'mail.api.admin.add_member',
	makeParams: () => ({ ...accountRequest }),
	onSuccess: () => {
		raiseToast(accountRequest.send_invite ? __('Member invited.') : __('Member added.'))
		emit('reload')
		show.value = false
	},
})
</script>
