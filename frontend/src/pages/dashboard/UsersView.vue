<template>
	<div class="flex items-center space-x-3">
		<FormControl v-model="search" :placeholder="__('Search')" class="w-80">
			<template #prefix>
				<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
			</template>
		</FormControl>
		<FormControl
			v-model="role"
			:placeholder="__('Member Role')"
			class="w-40"
			type="select"
			:options="ROLE_OPTIONS"
			@update:model-value="members.reload"
		/>
	</div>
	<ListView
		v-if="members?.data"
		class="flex-1"
		:columns="[{ label: __('User'), key: 'user' }]"
		:rows="members.data"
		:options="LIST_OPTIONS"
		row-key="name"
	>
		<ListHeader />
		<ListRows>
			<template v-if="members.data.length">
				<ListRow
					v-for="row in members.data"
					:key="row.name"
					:row="row"
					:class="{
						'hover:bg-surface-gray-1 cursor-pointer rounded':
							row.name !== tenantOwner.data,
					}"
					@click="openAccount(row.name)"
				>
					<div class="grid grid-cols-3">
						<div class="flex items-center space-x-2">
							<Avatar :image="row.user_image" :label="row.full_name" size="lg" />
							<div class="text-sm">
								<p class="font-medium">{{ row.full_name }}</p>
								<p class="text-ink-gray-5 mt-0.5">{{ row.name }}</p>
							</div>
						</div>
						<div class="mx-auto flex items-center">
							<Badge
								v-if="row.is_admin"
								:theme="row.name === tenantOwner.data ? 'orange' : 'blue'"
								:label="__(row.name === tenantOwner.data ? 'Owner' : 'Admin')"
							/>
						</div>
						<div class="ml-auto flex items-center">
							<Dropdown
								v-if="row.name !== tenantOwner.data"
								:options="dropdownOptions(row.name, row.is_admin)"
								:button="{
									icon: 'more-horizontal',
									variant: 'ghost',
								}"
								@click.stop
							/>
						</div>
					</div>
				</ListRow>
			</template>
			<ListEmptyState v-else />
		</ListRows>
	</ListView>
	<Dialog v-model="showRemoveMember" :options="removeMemberOptions" />
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useRouter } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import {
	Avatar,
	Badge,
	Dialog,
	Dropdown,
	FeatherIcon,
	FormControl,
	ListEmptyState,
	ListHeader,
	ListRow,
	ListRows,
	ListView,
	createResource,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'

const router = useRouter()
const user = inject('$user')
const { tenantOwner } = userStore()

const search = ref('')
const role = ref<'Mail User' | 'Mail Admin' | 'Both' | ''>('')
const showRemoveMember = ref(false)
const memberToBeRemoved = ref('')

const members = createResource({
	url: 'mail.api.admin.get_tenant_members',
	makeParams: () => ({
		tenant: user.data?.tenant,
		search: search.value,
		role: role.value === 'Both' ? '' : role.value,
	}),
	auto: true,
	cache: ['mailTenantMembers', user.data?.tenant, search.value, role.value],
})

watchDebounced(() => search.value, members.reload, { debounce: 300 })

const reloadMembers = () => members.reload()
defineExpose({ reloadMembers })

const editAdminRole = createResource({
	url: 'frappe.client.set_value',
	makeParams: ({ name, is_admin }: { name: string; is_admin: 0 | 1 }) => ({
		doctype: 'Mail Tenant Member',
		name: name,
		fieldname: 'is_admin',
		value: is_admin,
	}),
	onSuccess: () => {
		raiseToast(__('Role updated.'))
		members.reload()
	},
	onError: (error) => raiseToast(error.messages[0], 'error'),
})

const removeMember = createResource({
	url: 'frappe.client.delete',
	makeParams: () => ({ doctype: 'Mail Tenant Member', name: memberToBeRemoved.value }),
	onSuccess: () => {
		raiseToast(__('Member removed.'))
		showRemoveMember.value = false
		members.reload()
	},
	onError: (error) => raiseToast(error.messages[0], 'error'),
})

const openAccount = (account: string) => {
	if (account !== tenantOwner.data)
		router.push({ name: 'Member', params: { memberName: account } })
}

const dropdownOptions = (name: string, isAdmin: 0 | 1) => [
	{
		label: isAdmin ? __('Remove Admin') : __('Make Admin'),
		icon: isAdmin ? 'shield-off' : 'shield',
		onClick: () => editAdminRole.submit({ name, is_admin: !isAdmin }),
	},
	{
		label: __('Remove Member'),
		icon: 'user-x',
		onClick: () => {
			memberToBeRemoved.value = name
			showRemoveMember.value = true
		},
	},
]

const removeMemberOptions = computed(() => ({
	title: __('Remove Member'),
	message: __(`Are you sure you want to remove member ${memberToBeRemoved.value}?`),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: removeMember.submit }],
}))

const LIST_OPTIONS = {
	selectable: false,
	showTooltip: false,
	rowHeight: 50,
	emptyState: { description: __('No members found.') },
}

const ROLE_OPTIONS = [
	{ label: '', value: 'Both' },
	{ label: __('Mail User'), value: 'Mail User' },
	{ label: __('Mail Admin'), value: 'Mail Admin' },
]
</script>
