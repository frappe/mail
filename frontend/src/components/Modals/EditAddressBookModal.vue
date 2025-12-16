<template>
	<Dialog v-model="show" :options="options">
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="addressBook.name" :label="__('Name')" />
				<FormControl
					v-model="addressBook.description"
					type="textarea"
					:label="__('Description')"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import { Dialog, FormControl } from 'frappe-ui'

const show = defineModel<boolean>()

const { name, description } = defineProps<{ name: string; description: string }>()

const emit = defineEmits(['save'])

const addressBook = reactive({ name, description })

const options = computed(() => ({
	title: __('Edit General Information'),
	actions: [
		{
			label: __('Save'),
			variant: 'solid',
			disabled: addressBook.name === name && addressBook.description === description,
			onClick: () => {
				emit('save', addressBook)
				show.value = false
			},
		},
	],
}))
</script>
