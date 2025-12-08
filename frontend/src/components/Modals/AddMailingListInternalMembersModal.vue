<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('New Internal Members'),
			actions: [
				{
					label: __('Add'),
					variant: 'solid',
					disabled: members.length === 0,
					onClick: () => emit('add', members),
				},
			],
		}"
	>
		<template #body-content>
			<div ref="dialogBody" class="max-h-80 space-y-4 overflow-y-auto">
				<AddMailingListMemberInput
					v-for="(inputId, index) in inputFields"
					:key="inputId"
					:current-members
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
import { Dialog } from 'frappe-ui'

import AddMailingListMemberInput from '@/components/AddMailingListMemberInput.vue'

const show = defineModel<boolean>()

const { currentMembers } = defineProps<{ currentMembers: string[] }>()

const emit = defineEmits(['add'])

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

watch(
	() => show.value,
	(val) => {
		if (!val) return
		members.value = []
		inputFields.value = [0]
	},
)
</script>
