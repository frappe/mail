<template>
	<component
		:is="isMobile ? SendMailMobileLayout : Dialog"
		v-model="show"
		:options="{ title: __('Compose Mail'), size: '6xl' }"
		@send-mail="editor?.sendMail()"
		@discard-mail="editor?.discardMail()"
	>
		<template #body-content>
			<ComposeMailEditor
				v-if="show || !isMobile"
				ref="composeMailEditor"
				v-model="show"
				:mail-details
				:reload-mails="() => emit('reloadMails')"
				@discard-mail="emit('discardMail')"
			/>
		</template>
	</component>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, useTemplateRef } from 'vue'
import { Dialog } from 'frappe-ui'

import { useScreenSize } from '@/utils/composables'
import ComposeMailEditor from '@/components/ComposeMailEditor.vue'
import SendMailMobileLayout from '@/components/SendMailMobileLayout.vue'

import type { ComposeMailData } from '@/types'

const show = defineModel<boolean>()

const { mailDetails } = defineProps<{ mailDetails?: ComposeMailData }>()

const emit = defineEmits(['reloadMails', 'discardMail'])

const { isMobile } = useScreenSize()

const editor = useTemplateRef('composeMailEditor')

const handleKeydown = (e: KeyboardEvent) => {
	if (show.value && e.key === 'c' && !e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey) {
		const target = e.target as HTMLElement
		if (
			target.tagName !== 'INPUT' &&
			target.tagName !== 'TEXTAREA' &&
			!target.isContentEditable
		) {
			e.preventDefault()
			e.stopPropagation()
		}
	}
}

onMounted(() => window.addEventListener('keydown', handleKeydown, true))
onUnmounted(() => window.removeEventListener('keydown', handleKeydown, true))
</script>
