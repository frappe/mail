<template>
	<div class="flex items-center justify-between">
		<h1>{{ __('Signatures') }}</h1>
		<Button icon-left="plus" :label="__('New')" />
	</div>
	<FormControl :label="__('Color Scheme')" type="select" variant="outline" />
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { Button, FormControl } from 'frappe-ui'

const user = inject('$user')
</script>
