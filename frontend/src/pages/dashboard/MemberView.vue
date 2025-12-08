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
					<h2 class="border-b p-4">{{ __('General Information') }}</h2>
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
				<EmailListCard
					:rows="account.doc.emails"
					:title="__('Email Addresses')"
					:column-label="__('Email Address')"
					class="h-80"
					@add="addEmail(false)"
					@remove="
						(selections) =>
							(account.doc.emails = account.doc.emails.filter(
								(e) => !selections.has(e.value),
							))
					"
				/>
				<EmailListCard
					:rows="account.doc.lists"
					:title="__('Mailing Lists')"
					:column-label="__('Mailing List')"
					class="h-80"
					@add="addEmail(true)"
					@remove="
						(selections) =>
							(account.doc.lists = account.doc.lists.filter(
								(l) => !selections.has(l.value),
							))
					"
				/>
			</div>
		</template>
	</DashboardLayout>

	<AddEmailModal
		v-model="showAddEmail"
		:is-list="isAddList"
		@add-email="
			(value) =>
				isAddList ? account.doc.lists.push({ value }) : account.doc.emails.push({ value })
		"
	/>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Button, FormControl, createDocumentResource, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import DashboardLayout from '@/components/DashboardLayout.vue'
import EmailListCard from '@/components/EmailListCard.vue'
import AddEmailModal from '@/components/Modals/AddEmailModal.vue'

const { memberName } = defineProps<{ memberName: string }>()

const showAddEmail = ref(false)
const isAddList = ref(false)

const addEmail = (isList: boolean) => {
	isAddList.value = isList
	showAddEmail.value = true
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
