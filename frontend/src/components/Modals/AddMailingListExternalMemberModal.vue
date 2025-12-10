<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('New External Member'),
			actions: [
				{
					label: __('Add'),
					variant: 'solid',
					disabled: !email,
					onClick: () => emit('add', email),
				},
			],
		}"
	>
		<template #body-content>
			<FormControl
				v-model="email"
				type="email"
				:label="__('Email')"
				placeholder="johndoe@example.com"
			/>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, FormControl } from 'frappe-ui'

const show = defineModel<boolean>()

const emit = defineEmits(['add'])

const email = ref('')

watch(show, (val) => {
	if (val) email.value = ''
})
</script>
