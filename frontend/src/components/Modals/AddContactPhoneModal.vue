<template>
	<Dialog v-model="show" :options="options">
		<template #body-content>
			<div class="space-y-4">
				<FormControl v-model="email.number" type="tel" :label="__('Number')" required />
				<FormControl
					v-model="email.type"
					type="select"
					:label="__('Type')"
					:options="TYPE_OPTIONS"
					required
				/>
				<FormControl v-model="email.label" :label="__('Label')" />
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Dialog, FormControl } from 'frappe-ui'

const show = defineModel<boolean>()

const emit = defineEmits(['add'])

const DEFAULT_EMAIL = { number: '', type: 'Primary', label: '' }

const email = reactive({ ...DEFAULT_EMAIL })

const options = computed(() => ({
	title: __('Add Phone'),
	actions: [
		{
			label: __('Add'),
			variant: 'solid',
			disabled: !(email.number && email.type),
			onClick: () => {
				emit('add', email)
				show.value = false
			},
		},
	],
}))

watch(show, (val) => {
	if (val) Object.assign(email, DEFAULT_EMAIL)
})

const TYPE_OPTIONS = [
	{ label: __('Mobile'), value: 'Mobile' },
	{ label: __('Work'), value: 'Work' },
	{ label: __('Home'), value: 'Home' },
	{ label: __('Other'), value: 'Other' },
]
</script>
