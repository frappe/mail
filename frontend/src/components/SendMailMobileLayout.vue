<template>
	<div class="bg-surface-white fixed inset-0 z-10 flex flex-col" :class="{ hidden: !show }">
		<div class="sticky top-0 flex items-center border-b px-3 py-2.5">
			<Button variant="ghost" class="mr-2" @click="close">
				<template #icon>
					<X class="text-ink-gray-5 h-4 w-4" />
				</template>
			</Button>
			<h2>{{ __('Compose Mail') }}</h2>
			<Dropdown :options="ACTIONS">
				<Button variant="ghost" class="ml-auto mr-2">
					<template #icon>
						<EllipsisVertical class="text-ink-gray-5 h-4 w-4" />
					</template>
				</Button>
			</Dropdown>
			<Button variant="ghost" @click="emit('send-mail')">
				<template #icon>
					<SendHorizontal class="text-ink-gray-5 h-4 w-4" />
				</template>
			</Button>
		</div>
		<div class="px-3 py-2.5">
			<slot name="body-content" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import { EllipsisVertical, SendHorizontal, Trash2, X } from 'lucide-vue-next'
import { Button, Dropdown } from 'frappe-ui'

const show = defineModel<boolean>()

const emit = defineEmits(['send-mail', 'discard-mail'])

const close = () => {
	if (show.value) show.value = false
}

watch(show, (val) => {
	if (val) history.pushState(null, '')
})

onMounted(() => window.addEventListener('popstate', close))
onUnmounted(() => window.removeEventListener('popstate', close))

const ACTIONS = [
	{
		label: __('Discard'),
		onClick: () => emit('discard-mail'),
		icon: Trash2,
	},
]
</script>
