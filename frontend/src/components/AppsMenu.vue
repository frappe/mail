<template>
	<Popover placement="right-start" trigger="hover" :hover-delay="0.1" :leave-delay="0.1">
		<template #target="{ togglePopover, isOpen }">
			<button
				class="hover:bg-surface-gray-2 flex h-7 w-full items-center justify-between rounded px-2 text-base"
				:class="{ 'bg-surface-gray-2': isOpen }"
				@click.prevent="togglePopover()"
			>
				<div class="flex gap-2">
					<FeatherIcon name="grid" class="text-ink-gray-6 size-4" />
					<span class="text-ink-gray-7">{{ __('Apps') }}</span>
				</div>
				<FeatherIcon name="chevron-right" class="text-ink-gray-6 size-4" />
			</button>
		</template>
		<template #body>
			<div
				class="border-outline-gray-2 bg-surface-white auto-fill-[100px] dark:bg-surface-gray-1 flex w-48 flex-col rounded-lg border p-1.5 text-sm shadow-xl"
			>
				<a
					v-for="app in apps.data"
					:key="app.name"
					:href="app.route"
					class="hover:bg-surface-gray-2 flex items-center gap-2 rounded p-1"
				>
					<img class="size-6" :src="app.logo" />
					<span class="max-w-18 w-fulltruncate">{{ app.title }}</span>
				</a>
			</div>
		</template>
	</Popover>
</template>
<script setup lang="ts">
import { FeatherIcon, Popover, createResource } from 'frappe-ui'

const apps = createResource({ url: 'mail.api.get_apps', cache: 'otherApps', auto: true })
</script>
