<template>
	<DashboardLayout v-if="list.originalDoc" :breadcrumbs="BREADCRUMBS">
		<template #actions>
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
				<div class="rounded-md border">
					<h2 class="border-b p-4">{{ __('Mailing List Information') }}</h2>
					<div class="space-y-4 p-4">
						<FormControl
							v-model="list.doc.description"
							type="textarea"
							:label="__('Description')"
						/>
						<FormControl
							v-model="list.doc.total_members"
							:label="__('Member Count')"
							:readonly="true"
						/>
					</div>
				</div>
				<EmailListCard
					:rows="list.doc.emails"
					:title="__('Email Addresses')"
					:column-label="__('Email Address')"
					class="h-58"
					@add="showAddEmail = true"
					@remove="
						(selections) =>
							(list.doc.emails = list.doc.emails.filter(
								(e) => !selections.has(e.value),
							))
					"
				/>
			</div>
			<div class="flex flex-1 flex-col rounded-md border">
				<div class="h-13 my-auto flex shrink-0 items-center justify-between border-b px-4">
					<h2>{{ __('Members') }}</h2>
					<Dropdown :options="ADD_OPTIONS">
						<Button icon-left="plus" :label="__('Add')" variant="ghost" />
					</Dropdown>
				</div>
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
								row-key="value"
								class="flex-1"
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
														(m) => !selections.has(m.value),
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
			</div>
		</template>
	</DashboardLayout>

	<AddEmailModal
		v-model="showAddEmail"
		:is-list="false"
		@add-email="(value) => list.doc.emails.push({ value })"
	/>
	<AddMailingListInternalMembersModal
		v-if="list?.doc"
		v-model="showAddInternalMembers"
		:current-members="list.doc.members.map((m) => m.value)"
		@add="(members) => addMembers(members)"
	/>
	<AddMailingListExternalMemberModal
		v-model="showAddExternalMember"
		@add="(members) => addMembers([members], true)"
	/>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Globe, Home } from 'lucide-vue-next'
import {
	Button,
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
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import DashboardLayout from '@/components/DashboardLayout.vue'
import EmailListCard from '@/components/EmailListCard.vue'
import AddEmailModal from '@/components/Modals/AddEmailModal.vue'
import AddMailingListExternalMemberModal from '@/components/Modals/AddMailingListExternalMemberModal.vue'
import AddMailingListInternalMembersModal from '@/components/Modals/AddMailingListInternalMembersModal.vue'

const { listName } = defineProps<{ listName: string }>()

const router = useRouter()

const tabIndex = ref(0)
const listView = ref(null)

const search = ref('')

const showAddEmail = ref(false)
const showAddInternalMembers = ref(false)
const showAddExternalMember = ref(false)

const list = createDocumentResource({
	doctype: 'Mail Principal',
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

const memberList = computed(() =>
	(tabIndex.value ? list.doc.external_members : list.doc.members).filter((m) =>
		m.value.toLowerCase().includes(search.value.toLowerCase()),
	),
)

const addMembers = (members: string[], external = false) => {
	const membersObj = members.map((m) => ({ value: m }))
	if (external) {
		list.doc.external_members.push(...membersObj)
		showAddExternalMember.value = false
	} else {
		list.doc.members.push(...membersObj)
		showAddInternalMembers.value = false
	}
}

const LIST_COLUMNS = [{ label: __('Name'), key: 'value' }]

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
</script>
