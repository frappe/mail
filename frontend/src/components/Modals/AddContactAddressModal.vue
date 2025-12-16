<template>
	<Dialog v-model="show" :options="options">
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="address.type"
					type="select"
					:label="__('Type')"
					:options="TYPE_OPTIONS"
					required
				/>
				<FormControl v-model="address.street" :label="__('Street')" required />
				<FormControl v-model="address.locality" :label="__('Locality')" />
				<FormControl v-model="address.region" :label="__('Region')" />
				<FormControl v-model="address.postcode" :label="__('Postcode')" />
				<FormControl v-model="address.country" :label="__('Country')" />
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { Dialog, FormControl } from 'frappe-ui'

const show = defineModel<boolean>()

const emit = defineEmits(['add'])

const DEFAULT_ADDRESS = {
	type: 'Home',
	street: '',
	locality: '',
	region: '',
	postcode: '',
	country: '',
}

const address = reactive({ ...DEFAULT_ADDRESS })

const options = computed(() => ({
	title: __('Add Address'),
	actions: [
		{
			label: __('Add'),
			variant: 'solid',
			disabled: !(address.type && address.street),
			onClick: () => {
				emit('add', address)
				show.value = false
			},
		},
	],
}))

watch(show, (val) => {
	if (val) Object.assign(address, DEFAULT_ADDRESS)
})

const TYPE_OPTIONS = [
	{ label: __('Home'), value: 'Home' },
	{ label: __('Work'), value: 'Work' },
	{ label: __('Other'), value: 'Other' },
]
</script>
