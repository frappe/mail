<template>
	<div class="flex space-x-4">
		<Autocomplete
			v-model="email"
			:placeholder="__('Email')"
			:options="filteredOptions"
			:disabled="!!email"
			class="flex-1"
			@update:model-value="(option) => handleSelect(option)"
		/>
		<Button icon="x" :disabled="isLastInput" @click="emit('remove-input', email)" />
	</div>
</template>

<script lang="ts" setup>
import { computed, ref, watch } from 'vue'
import { Autocomplete, Button, createResource } from 'frappe-ui'

const { selectedMembers, currentMembers } = defineProps<{
	currentMembers?: string[]
	selectedMembers: string[]
	isLastInput: boolean
}>()

const emit = defineEmits(['email-selected', 'remove-input'])

const email = ref('')
const search = ref('')

const invalidMembers = computed(() => [...selectedMembers, ...(currentMembers || [])])

const eligibleMembers = createResource({
	url: 'mail.api.admin.get_eligible_members',
	makeParams: () => ({
		search: search.value,
		exclude: invalidMembers.value,
	}),
	auto: true,
})

watch(invalidMembers, () => eligibleMembers.reload(), { deep: true })

const filteredOptions = computed(() =>
	(eligibleMembers.data || []).map((m: { name: string; description: string }) => ({
		label: m.name,
		value: m.name,
		description: m.description,
	})),
)

const handleSelect = (option: { label: string; value: string }) => {
	if (option?.value) {
		email.value = option.value
		emit('email-selected', option.value)
	}
}
</script>
