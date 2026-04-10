<template>
	<Dialog v-model="show" :options="options">
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="contact.fullName" :label="__('Name')" />
				<FormControl
					v-model="contact.kind"
					type="select"
					:label="__('Kind')"
					:options="KIND_OPTIONS"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import { Dialog, FormControl } from 'frappe-ui'

const show = defineModel<boolean>()

const { fullName, kind } = defineProps<{ fullName?: string; kind: string }>()

const emit = defineEmits(['save'])

const contact = reactive({ fullName, kind })

const options = computed(() => ({
	title: __('Edit General Information'),
	actions: [
		{
			label: __('Save'),
			variant: 'solid',
			disabled: contact.fullName === fullName && contact.kind === kind,
			onClick: () => {
				emit('save', contact)
				show.value = false
			},
		},
	],
}))

const KIND_OPTIONS = [
	{ label: __('Individual'), value: 'Individual' },
	{ label: __('Group'), value: 'Group' },
]
</script>
