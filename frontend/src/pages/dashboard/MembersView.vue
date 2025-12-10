<template>
	<DashboardLayout
		:breadcrumbs="[{ label: __('Members') }]"
		:button-label="__('Add Member')"
		:button-action="() => (showAddMember = true)"
		:remove-spacing="true"
	>
		<Tabs
			v-model="tabIndex"
			:tabs="[
				{ label: __('Users'), icon: Users, index: 0 },
				{ label: __('Invites'), icon: Mails, index: 1 },
			]"
		>
			<template #tab-panel="{ tab }">
				<div class="flex flex-1 flex-col space-y-5 overflow-y-auto p-5">
					<UsersView v-if="tab.index === 0" ref="usersView" />
					<InvitesView v-else ref="invitesView" />
				</div>
			</template>
		</Tabs>
	</DashboardLayout>
	<AddMemberModal v-model="showAddMember" @reload="reload" />
</template>
<script setup lang="ts">
import { ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Mails, Users } from 'lucide-vue-next'
import { Tabs } from 'frappe-ui'

import InvitesView from '@/pages/dashboard/InvitesView.vue'
import UsersView from '@/pages/dashboard/UsersView.vue'
import DashboardLayout from '@/components/DashboardLayout.vue'
import AddMemberModal from '@/components/Modals/AddMemberModal.vue'

const route = useRoute()
const router = useRouter()

const tabIndex = ref(0)

watch(tabIndex, (val) => router.push({ name: val ? 'Invites' : 'Members' }))

watch(
	() => route.name,
	(val) => (tabIndex.value = val === 'Members' ? 0 : 1),
	{ immediate: true },
)

// add/invite members

const showAddMember = ref(false)

const usersView = useTemplateRef('usersView')
const invitesView = useTemplateRef('invitesView')

const reload = () => {
	if (tabIndex.value === 0) usersView?.value?.reloadMembers()
	else invitesView?.value?.reloadInvites()
}
</script>
