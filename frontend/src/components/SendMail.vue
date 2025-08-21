<template>
	<component
		:is="isMobile ? SendMailMobileLayout : Dialog"
		v-model="show"
		:options="{ title: __('Compose Mail'), size: '4xl' }"
		@send-mail="sendMail"
		@discard-mail="discardMail"
	>
		<template #body-content>
			<ComposeMailEditor
				v-model="show"
				:mail-i-d
				:mail-details
				@reload-mails="emit('reloadMails')"
			/>
		</template>
	</component>
</template>

<script setup lang="ts">
import { Dialog } from 'frappe-ui'

import { useScreenSize } from '@/utils/composables'
import ComposeMailEditor from '@/components/ComposeMailEditor.vue'
import SendMailMobileLayout from '@/components/SendMailMobileLayout.vue'

import type { ComposeMailData } from '@/types'

const show = defineModel<boolean>()

const { mailID, mailDetails } = defineProps<{ mailID?: string; mailDetails?: ComposeMailData }>()

const emit = defineEmits(['reloadMails'])

const { isMobile } = useScreenSize()
</script>
