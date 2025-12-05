<template>
	<DashboardLayout
		:breadcrumbs="BREADCRUMBS"
		:badge-label="isAdmin.data === 1 ? __('Admin') : ''"
		badge-theme="blue"
	>
		<template #actions>
			<Button
				variant="solid"
				:label="__('Save')"
				:loading="account.save.loading || editIsAdmin.loading"
				:disabled="
					account.get.loading || isAdmin.loading || !(isAccountDirty || isRoleDirty)
				"
				@click="save"
			/>
		</template>
		<template #default>
			<div v-if="account.doc" class="grid grid-cols-2 gap-5">
				<div class="rounded-md border">
					<h2 class="border-b p-4">{{ __('Member Information') }}</h2>
					<div class="space-y-4 p-4">
						<FormControl
							v-model="role"
							type="combobox"
							:label="__('Role')"
							:options="['Mail User', 'Mail Admin']"
							:open-on-click="true"
						/>
						<FormControl
							v-model="account.doc.description"
							type="textarea"
							:label="__('Description')"
						/>
					</div>
				</div>
				<div class="rounded-md border">
					<div class="flex items-center justify-between border-b p-4">
						<h2>{{ __('Quota Usage') }}</h2>
						<!-- <Button variant="ghost" :label="__('Set Restriction')" /> -->
					</div>
					<div class="h-36 space-y-4 px-4 py-12">
						<div class="w-full space-y-2">
							<span class="text-ink-gray-5 line-clamp-1 text-center text-lg">
								{{ '18% of 10GB used' }}
							</span>
							<div class="bg-surface-gray-4 h-1.5 w-auto rounded-full">
								<div
									class="h-1.5 rounded-full"
									:class="18 > 80 ? 'bg-surface-red-6' : 'bg-surface-gray-7'"
									:style="{ width: `${18}%`, maxWidth: '100%' }"
								/>
							</div>
						</div>
					</div>
				</div>
				<div class="flex h-80 shrink-0 flex-col rounded-md border">
					<div class="flex items-center justify-between border-b px-4 py-2.5">
						<h2>{{ __('Email Addresses') }}</h2>
						<Button
							variant="ghost"
							:label="__('Add')"
							icon-left="plus"
							@click="addEmail(false)"
						/>
					</div>
					<ListView
						:columns="[{ label: __('Email Address'), key: 'value' }]"
						:rows="account.doc.emails"
						row-key="value"
						:options="{
							emptyState: { title: '', description: 'No email addresses.' },
						}"
						class="flex-1 overflow-auto p-4"
					>
						<ListHeader />
						<ListRows v-if="account.doc.emails.length" />
						<ListEmptyState v-else />
						<ListSelectBanner>
							<template #actions="{ selections, unselectAll }">
								<Button
									variant="ghost"
									:label="__('Remove')"
									theme="red"
									@click="
										() => {
											account.doc.emails = account.doc.emails.filter(
												(e) => !selections.has(e.value),
											)
											unselectAll()
										}
									"
								/>
							</template>
						</ListSelectBanner>
					</ListView>
				</div>
				<div class="flex h-80 shrink-0 flex-col rounded-md border">
					<div class="flex items-center justify-between border-b px-4 py-2.5">
						<h2>{{ __('Mailing Lists') }}</h2>
						<Button
							variant="ghost"
							:label="__('Add')"
							icon-left="plus"
							@click="addEmail(true)"
						/>
					</div>
					<ListView
						:columns="[{ label: __('Mailing List'), key: 'value' }]"
						:rows="account.doc.lists"
						row-key="value"
						:options="{ emptyState: { title: '', description: 'No mailing lists.' } }"
						class="flex-1 overflow-auto p-4"
					>
						<ListHeader />
						<ListRows v-if="account.doc.lists.length" />
						<ListEmptyState v-else />
						<ListSelectBanner>
							<template #actions="{ selections, unselectAll }">
								<Button
									variant="ghost"
									:label="__('Remove')"
									theme="red"
									@click="
										() => {
											account.doc.lists = account.doc.lists.filter(
												(l) => !selections.has(l.value),
											)
											unselectAll()
										}
									"
								/>
							</template>
						</ListSelectBanner>
					</ListView>
				</div>
			</div>
		</template>
	</DashboardLayout>

	<AddMemberEmail
		v-model="showAddMemberEmail"
		:is-list="isAddList"
		@add-email="
			(value) =>
				isAddList ? account.doc.lists.push({ value }) : account.doc.emails.push({ value })
		"
	/>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
	Button,
	FormControl,
	ListEmptyState,
	ListHeader,
	ListRows,
	ListSelectBanner,
	ListView,
	createDocumentResource,
	createResource,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import DashboardLayout from '@/components/DashboardLayout.vue'
import AddMemberEmail from '@/components/Modals/AddMemberEmail.vue'

const { memberName } = defineProps<{ memberName: string }>()

const showAddMemberEmail = ref(false)
const isAddList = ref(false)

const addEmail = (isList: boolean) => {
	isAddList.value = isList
	showAddMemberEmail.value = true
}

const isAdmin = createResource({
	url: 'frappe.client.get_value',
	makeParams: () => ({
		doctype: 'Mail Tenant Member',
		fieldname: 'is_admin',
		filters: memberName,
		as_dict: false,
	}),
	onSuccess: (data) => (role.value = data === 1 ? 'Mail Admin' : 'Mail User'),
	auto: true,
	cache: ['isAdmin', memberName],
})

const role = ref(isAdmin?.data ? 'Mail Admin' : 'Mail User')

const account = createDocumentResource({
	doctype: 'Mail Principal',
	name: memberName,
	setValue: {
		onSuccess: () => raiseToast(__('Account updated.')),
		onError: (error) => {
			raiseToast(error.messages[0], 'error')
			account.reload()
		},
	},
})

const editIsAdmin = createResource({
	url: 'frappe.client.set_value',
	makeParams: ({ name, is_admin }: { name: string; is_admin: 0 | 1 }) => ({
		doctype: 'Mail Tenant Member',
		name: name,
		fieldname: 'is_admin',
		value: is_admin,
	}),
	onSuccess: () => {
		isAdmin.reload()
		raiseToast(__('Role updated.'))
	},
	onError: (error) => raiseToast(error.messages[0], 'error'),
})

const isRoleDirty = computed(
	() => (isAdmin.data === 1 ? 'Mail Admin' : 'Mail User') !== role.value,
)

const isAccountDirty = computed(
	() => JSON.stringify(account.doc) !== JSON.stringify(account.originalDoc),
)

const save = async () => {
	if (isRoleDirty.value)
		editIsAdmin.submit({ name: memberName, is_admin: role.value === 'Mail User' ? 0 : 1 })
	if (isAccountDirty.value) account.save.submit()
}

const BREADCRUMBS = [{ label: __('Members'), route: '/dashboard/members' }, { label: memberName }]
</script>
