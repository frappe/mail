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
				<DashboardCard
					:title="__('General Information')"
					:button-label="__('Edit')"
					@action="showEditGeneral = true"
				>
					<InformationField :label="__('Role')" :value="role" />
					<InformationField
						:label="__('Description')"
						:value="account.doc.description"
					/>
					<InformationField
						v-if="userDates?.data?.last_active"
						:label="__('Last Active')"
						:value="dayjs(userDates.data.last_active).format('MMM D YYYY, h:mm A')"
					/>
					<InformationField
						v-if="userDates?.data?.creation"
						:label="__('Joined On')"
						:value="dayjs(userDates.data.creation).format('MMM D YYYY, h:mm A')"
					/>
					<InformationField :label="__('Organization')" :value="user.data.tenant_name" />
				</DashboardCard>
				<DashboardCard
					:title="__('Quota Usage')"
					:button-label="__('Edit')"
					@action="showEditQuota = true"
				>
					<div class="flex flex-1 items-center justify-center">
						<QuotaProgressBar
							:quota="Number(account.doc.quota) / GB"
							:used-quota="account.doc.used_quota / GB"
						/>
					</div>
				</DashboardCard>
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

	<Dialog
		v-if="account?.originalDoc && isAdmin?.data !== undefined"
		v-model="showEditGeneral"
		:options="{
			title: __('Edit General Information'),
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled:
						account.doc.description === account.originalDoc.description &&
						!isRoleDirty,
					onClick: () => {
						save()
						showEditGeneral = false
					},
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="role"
					type="combobox"
					:label="__('Role')"
					:options="['Mail User', 'Mail Admin']"
					:open-on-click="true"
				/>
				<FormControl
					v-model="account.doc.description"
					:label="__('Description')"
					type="textarea"
				/>
			</div>
		</template>
	</Dialog>
	<Dialog
		v-if="account?.doc"
		v-model="showEditQuota"
		:options="{
			title: __('Edit Quota Usage'),
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled:
						quota < 0 ||
						Number(account.doc.quota) === (viewQuotaInBytes ? quota : quota * GB),
					onClick: () => {
						showEditQuota = false
						account.doc.quota = viewQuotaInBytes ? quota : quota * GB
						account.save.submit()
					},
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<Switch
					v-model="viewQuotaInBytes"
					:label="__('View in Bytes')"
					class="hover:!bg-surface-white !cursor-default !p-0"
				/>
				<FormControl
					type="number"
					:value="
						viewQuotaInBytes ? account.doc.used_quota : account.doc.used_quota / GB
					"
					:label="
						viewQuotaInBytes
							? __('Storage Used (in Bytes)')
							: __('Storage Used (in GB)')
					"
					:readonly="true"
				/>
				<hr />
				<Switch
					v-model="setQuotaRestriction"
					:label="__('Set Restriction')"
					class="hover:!bg-surface-white !cursor-default !p-0"
					@update:model-value="
						(val: boolean) => (quota = val ? (viewQuotaInBytes ? GB : 1) : 0)
					"
				/>
				<FormControl
					v-if="setQuotaRestriction"
					v-model="quota"
					type="number"
					:label="viewQuotaInBytes ? __('Quota (in Bytes)') : __('Quota (in GB)')"
				/>
			</div>
		</template>
	</Dialog>
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
import { computed, inject, ref, watch } from 'vue'
import {
	Button,
	Dialog,
	FormControl,
	Switch,
	createDocumentResource,
	createResource,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import DashboardCard from '@/components/DashboardCard.vue'
import DashboardLayout from '@/components/DashboardLayout.vue'
import EmailListCard from '@/components/EmailListCard.vue'
import InformationField from '@/components/InformationField.vue'
import AddEmailModal from '@/components/Modals/AddEmailModal.vue'
import QuotaProgressBar from '@/components/QuotaProgressBar.vue'

const { memberName } = defineProps<{ memberName: string }>()

const user = inject('$user')
const dayjs = inject('$dayjs')

const showEditGeneral = ref(false)

const showEditQuota = ref(false)
const setQuotaRestriction = ref(false)
const viewQuotaInBytes = ref(false)
const quota = ref(0)

const showAddEmail = ref(false)
const isAddList = ref(false)

watch(viewQuotaInBytes, (val: boolean) => {
	if (val) quota.value *= GB
	else quota.value /= GB
})

watch(showEditQuota, (val: boolean) => {
	if (!val) return

	setQuotaRestriction.value = !!account.doc.quota
	viewQuotaInBytes.value = false
	quota.value = account.doc.quota / GB
})

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

const userDates = createResource({
	url: 'frappe.client.get_value',
	makeParams: () => ({
		doctype: 'User',
		fieldname: ['creation', 'last_active'],
		filters: memberName,
	}),
	auto: true,
	cache: ['userDates', memberName],
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

const GB = 1024 * 1024 * 1024
</script>
