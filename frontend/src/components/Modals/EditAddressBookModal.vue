<template>
	<Dialog v-model="show" :options="options">
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="addressBook.name"
					:label="__('Name')"
					:placeholder="__('Work Contacts')"
				/>
				<FormControl
					v-model="addressBook.description"
					type="textarea"
					:label="__('Description')"
					:placeholder="__('All my work-related contacts')"
				/>
				<FormControl
					v-model="addressBook.isDefault"
					type="checkbox"
					:label="__('Set as Default')"
					:disabled="isDefault"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Dialog, FormControl } from 'frappe-ui'

const show = defineModel<boolean>()

const { name, description, isDefault } = defineProps<{
	name: string
	description: string
	isDefault: boolean
}>()

const emit = defineEmits(['save'])

const addressBook = reactive({ name, description, isDefault })

const options = computed(() => ({
	title: __('Edit General Information'),
	actions: [
		{
			label: __('Save'),
			variant: 'solid',
			disabled:
				addressBook.name === name &&
				addressBook.description === description &&
				addressBook.isDefault === isDefault,
			onClick: () => {
				emit('save', addressBook)
				show.value = false
			},
		},
	],
}))

watch(show, (val) => {
	if (val) Object.assign(addressBook, { name, description, isDefault })
})
</script>
