<template>
	<div class="flex h-full flex-col">
		<header class="flex items-center border-b px-3 py-2.5 sm:px-5">
			<Breadcrumbs :items="breadcrumbs" class="mr-2" />
			<Badge v-if="badgeLabel" :label="badgeLabel" :theme="badgeTheme" />
			<div class="ml-auto flex space-x-2">
				<slot name="actions">
					<Button
						v-if="buttonLabel"
						:label="buttonLabel"
						icon-left="plus"
						@click="buttonAction"
					/>
				</slot>
			</div>
		</header>
		<div
			class="flex flex-1 flex-col overflow-y-auto"
			:class="{ 'space-y-5 p-5': !removeSpacing }"
		>
			<slot />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Badge, Breadcrumbs, Button } from 'frappe-ui'

const { removeSpacing = false } = defineProps<{
	breadcrumbs: { label: string; route?: string }[]
	buttonLabel?: string
	buttonAction?: () => void
	badgeLabel?: string
	badgeTheme?: 'green' | 'red' | 'gray' | 'orange' | 'blue'
	removeSpacing?: boolean
}>()
</script>
