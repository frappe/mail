<template>
	<div class="flex space-x-4">
		<Link
			v-model="email"
			:placeholder="__('Email')"
			doctype="Mail Tenant Member"
			:filters="{ tenant: user.data.tenant, name: ['not in', invalidMembers] }"
			:disabled="!!email"
			class="flex-1"
			@update:model-value="(value: string) => emit('email-selected', value)"
		/>
		<Button icon="x" :disabled="isLastInput" @click="emit('remove-input', email)" />
	</div>
</template>

<script lang="ts" setup>
import { computed, inject, ref } from 'vue'
import { Link } from 'frappe-ui/frappe'
import { Button } from 'frappe-ui'

import { userStore } from '@/stores/user'

import type { UserResource } from '@/types'

const { selectedMembers, currentMembers } = defineProps<{
	currentMembers?: string[]
	selectedMembers: string[]
	isLastInput: boolean
}>()

const emit = defineEmits(['email-selected', 'remove-input'])

const user = inject('$user') as UserResource
const { tenantOwner } = userStore()

const email = ref('')

const invalidMembers = computed(() => [
	...selectedMembers,
	...(currentMembers || []),
	...[tenantOwner.data],
])
</script>
