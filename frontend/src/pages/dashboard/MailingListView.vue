<template>
	<DashboardLayout v-if="list.originalDoc" :breadcrumbs="BREADCRUMBS">
		<template #actions>
			<Button
				variant="ghost"
				theme="red"
				:label="__('Delete')"
				@click="showDeleteList = true"
			/>
			<Button
				variant="solid"
				:label="__('Save')"
				:loading="list.save.loading"
				:disabled="JSON.stringify(list.doc) === JSON.stringify(list.originalDoc)"
				@click="list.save.submit()"
			/>
		</template>
		<template #default>
			<div v-if="list.doc" class="grid grid-cols-2 gap-5">
				<DashboardCard
					:title="__('General Information')"
					:button-label="__('Edit')"
					class="h-[14.5rem]"
					@action="showEditGeneral = true"
				>
					<InformationField
						:label="__('Total Members')"
						:value="list.doc.total_members.toString()"
					/>
					<InformationField :label="__('Description')" :value="list.doc.description" />
					<InformationField
						v-if="listCreation?.data"
						:label="__('Created On')"
						:value="dayjs(listCreation.data).format('MMM D YYYY, h:mm A')"
					/>
				</DashboardCard>
				<ListCard
					:rows="list.doc.emails"
					:title="__('Email Addresses')"
					:column-label="__('Email Address')"
					row="email"
					class="h-[14.5rem]"
					@add="showAddEmail = true"
					@remove="
						(selections) =>
							(list.doc.emails = list.doc.emails.filter(
								(e) => !selections.has(e.idx),
							))
					"
				/>
			</div>
			<DashboardCard :title="__('Members')" class="flex-1">
				<template #actions>
					<Dropdown :options="ADD_OPTIONS">
						<Button :label="__('Add')" variant="ghost" />
					</Dropdown>
				</template>
				<Tabs
					v-model="tabIndex"
					:tabs="[
						{ label: __('Internal'), icon: Home, index: 0 },
						{ label: __('External'), icon: Globe, index: 1 },
					]"
					class="flex h-full flex-col"
				>
					<template #tab-panel>
						<div class="flex flex-1 flex-col space-y-4 p-4">
							<FormControl v-model="search" :placeholder="__('Search')" class="w-80">
								<template #prefix>
									<FeatherIcon name="search" class="text-ink-gray-5 w-4" />
								</template>
							</FormControl>

							<ListView
								v-if="memberList"
								ref="listView"
								:columns="LIST_COLUMNS"
								:rows="memberList"
								:options="LIST_OPTIONS"
								row-key="member"
								class="max-h-[50rem] min-h-72 flex-1 overflow-auto"
							>
								<ListHeader />
								<ListRows v-if="memberList.length" />
								<ListEmptyState v-else />
								<ListSelectBanner>
									<template #actions="{ selections, unselectAll }">
										<Button
											variant="ghost"
											theme="red"
											:label="__('Remove')"
											@click="
												() => {
													list.doc[
														tabIndex ? 'external_members' : 'members'
													] = memberList.filter(
														(m) => !selections.has(m.member),
													)
													unselectAll()
												}
											"
										/>
									</template>
								</ListSelectBanner>
							</ListView>
						</div>
					</template>
				</Tabs>
			</DashboardCard>
		</template>
	</DashboardLayout>

	<Dialog
		v-if="list?.originalDoc"
		v-model="showEditGeneral"
		:options="{
			title: __('Edit General Information'),
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					disabled: list.doc.description === list.originalDoc.description,
					onClick: () => {
						list.save.submit()
						showEditGeneral = false
					},
				},
			],
		}"
	>
		<template #body-content>
			<FormControl
				v-model="list.doc.description"
				:label="__('Description')"
				type="textarea"
			/>
		</template>
	</Dialog>
	<AddEmailModal
		v-model="showAddEmail"
		:is-list="false"
		@add-email="(value) => list.doc.emails.push({ email: value })"
	/>
	<AddMailingListInternalMembersModal
		v-if="list?.doc"
		v-model="showAddInternalMembers"
		:current-members="list.doc.members.map((m) => m.member)"
		@add="(members) => addMembers(members)"
	/>
	<AddMailingListExternalMemberModal
		v-model="showAddExternalMember"
		@add="(members) => addMembers([members], true)"
	/>
	<Dialog v-model="showDeleteList" :options="DELETE_LIST_OPTIONS" />
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Globe, Home } from 'lucide-vue-next'
import {
	Button,
	Dialog,
	Dropdown,
	FeatherIcon,
	FormControl,
	ListEmptyState,
	ListHeader,
	ListRows,
	ListSelectBanner,
	ListView,
	Tabs,
	createDocumentResource,
	createResource,
	usePageMeta,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import DashboardCard from '@/components/DashboardCard.vue'
import DashboardLayout from '@/components/DashboardLayout.vue'
import InformationField from '@/components/InformationField.vue'
import ListCard from '@/components/ListCard.vue'
import AddEmailModal from '@/components/Modals/AddEmailModal.vue'
import AddMailingListExternalMemberModal from '@/components/Modals/AddMailingListExternalMemberModal.vue'
import AddMailingListInternalMembersModal from '@/components/Modals/AddMailingListInternalMembersModal.vue'

const { listName } = defineProps<{ listName: string }>()

usePageMeta(() => ({ title: listName }))

const router = useRouter()
const dayjs = inject('$dayjs')

const tabIndex = ref(0)

const search = ref('')

const showEditGeneral = ref(false)
const showDeleteList = ref(false)
const showAddEmail = ref(false)
const showAddInternalMembers = ref(false)
const showAddExternalMember = ref(false)

const list = createDocumentResource({
	doctype: 'Principal',
	name: listName,
	setValue: {
		onSuccess: () => raiseToast(__('Mailing list updated.')),
		onError(error) {
			raiseToast(error.messages[0], 'error')
			list.reload()
		},
	},
	onError: () => router.replace({ name: 'MailingLists' }),
})

const listCreation = createResource({
	url: 'frappe.client.get_value',
	makeParams: () => ({
		doctype: 'Principal Settings',
		fieldname: 'creation',
		filters: { principal_name: listName, principal_type: 'List' },
		as_dict: false,
	}),
	auto: true,
	cache: ['listCreation', listName],
})

const memberList = computed(() =>
	(tabIndex.value ? list.doc.external_members : list.doc.members).filter((m) =>
		m.member.toLowerCase().includes(search.value.toLowerCase()),
	),
)

const addMembers = (members: string[], external = false) => {
	const membersObj = members.map((m) => ({ member: m }))
	if (external) {
		list.doc.external_members.push(...membersObj)
		showAddExternalMember.value = false
	} else {
		list.doc.members.push(...membersObj)
		showAddInternalMembers.value = false
	}
}

const LIST_COLUMNS = [{ label: __('Name'), key: 'member' }]

const ADD_OPTIONS = [
	{
		label: __('Internal'),
		icon: Home,
		onClick: () => (showAddInternalMembers.value = true),
	},
	{
		label: __('External'),
		icon: Globe,
		onClick: () => (showAddExternalMember.value = true),
	},
]

const BREADCRUMBS = [
	{ label: __('Mailing Lists'), route: '/dashboard/mailing-lists' },
	{ label: listName },
]

const LIST_OPTIONS = { showTooltip: false, emptyState: { description: __('No members found.') } }

const deleteList = createResource({
	url: 'mail.api.admin.delete_mailing_lists',
	makeParams: () => ({ names: [listName] }),
	onSuccess: () => {
		raiseToast(__('Mailing list deleted.'))
		router.push({ name: 'MailingLists' })
	},
	onError: (error) => {
		showDeleteList.value = false
		raiseToast(error.messages[0], 'error')
	},
})

const DELETE_LIST_OPTIONS = {
	title: __('Delete Mailing List'),
	message: __(
		'Are you sure you want to delete this mailing list? This action cannot be undone.',
	),
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: deleteList.submit }],
}
</script>
