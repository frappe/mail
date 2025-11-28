<template>
	<Dialog
		v-model="show"
		:options="{
			title: type === 'Mail Account' ? __('Add Internal Members') : __('Add Groups'),
			actions: [
				{
					label: __('Confirm'),
					variant: 'solid',
					disabled: members.length === 0,
					onClick: addMembers.submit,
				},
			],
		}"
	>
		<template #body-content>
			<div ref="dialogBody" class="max-h-80 space-y-4 overflow-y-auto">
				<AddMailingListMemberInput
					v-for="(inputId, index) in inputFields"
					:key="inputId"
					:type="type"
					:current-members="currentMembers.data"
					:selected-members="members"
					:is-last-input="index === inputFields.length - 1"
					@email-selected="(email) => handleEmailSelected(email, index)"
					@remove-input="(email) => removeInput(email, index)"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { Dialog, createResource, useList } from 'frappe-ui'

import { raiseToast } from '@/utils'
import AddMailingListMemberInput from '@/components/AddMailingListMemberInput.vue'

const { list, type } = defineProps<{ list: string; type: 'Mail Account' | 'Mail Group' }>()

const emit = defineEmits(['reloadMembers'])

const show = defineModel<boolean>()

const dialogBody = ref<HTMLElement | null>(null)

const inputFields = ref([0])
const members = ref<string[]>([])

const handleEmailSelected = (email: string, index: number) => {
	members.value.push(email)
	if (index === inputFields.value.length - 1) addInput()
}

const addInput = () => {
	inputFields.value.push(inputFields.value.length)
	nextTick(() => {
		if (dialogBody.value)
			dialogBody.value.scrollTo({ top: dialogBody.value.scrollHeight, behavior: 'smooth' })
	})
}

const removeInput = (email: string, index: number) => {
	members.value = members.value.filter((member) => member !== email)
	inputFields.value.splice(index, 1)
}

const currentMembers = useList({
	doctype: 'Mailing List Member',
	immediate: false,
	fields: ['member_name as name'],
	filters: { mailing_list: list },
	limit: 1000,
	cacheKey: ['mailingListMembers', list],
	transform: (data) => {
		data = data.map((member) => member.name)
		data.push(list)
		return data
	},
})

const addMembers = createResource({
	url: 'mail.api.admin.add_list_members',
	makeParams: () => ({ list, type, members: members.value }),
	onSuccess: () => {
		raiseToast(__('Members added.'))
		show.value = false
		emit('reloadMembers')
	},
	onError: (error) => raiseToast(error.message, 'error'),
})

watch(
	() => show.value,
	(val) => {
		if (!val) return
		members.value = []
		inputFields.value = [0]
		currentMembers.fetch()
	},
)
</script>
