<script setup lang="ts">
import { computed } from 'vue'
import { Check, Minus, X } from 'lucide-vue-next'
import { Avatar, Button } from 'frappe-ui'

import { extractNameFromEmail } from '@/utils/format'
import { userStore } from '@/stores/user'

const { participants, dontShowRemove } = defineProps<{
	participants: any[]
	dontShowRemove?: boolean
}>()

defineEmits(['removeParticipant'])

const { identities } = userStore()

const organizer = computed(() => participants.find((p) => p.isOrganizer)?.email)

const isUserOrganizer = computed(() =>
	identities.data.some((id) => id.email === organizer.value?.replace('mailto:', '')),
)

const showRemoveParticipant = (participant: any) =>
	!participant.isOrganizer && (isUserOrganizer.value || participant.isNew) && !dontShowRemove

const getParticipantStatusValues = (status: string) => {
	if (status === 'ACCEPTED') return { icon: Check, class: 'bg-surface-green-1 text-ink-green-3' }
	if (status === 'TENTATIVE') return { icon: Minus, class: 'bg-surface-gray-1 text-ink-gray-6' }
	return { icon: X, class: 'bg-surface-red-1 text-ink-red-3' }
}
</script>
<template>
	<div v-for="p in participants" :key="p.email">
		<div class="flex items-center justify-between text-left">
			<div class="flex items-center space-x-2">
				<Avatar :image="p.user_image" :label="p._name || p.email" size="xl" />
				<div class="flex flex-col space-y-0.5">
					<div class="flex items-center space-x-1">
						<span class="text-sm font-medium">
							{{ extractNameFromEmail(p._name || p.email) }}
						</span>
						<span v-if="p.email === organizer" class="text-ink-gray-4 text-xs">
							({{ __('Organizer') }})
						</span>

						<div
							v-if="
								p.participation_status && p.participation_status !== 'NEEDS-ACTION'
							"
							class="rounded-full p-px"
							:class="getParticipantStatusValues(p.participation_status).class"
						>
							<component
								:is="getParticipantStatusValues(p.participation_status).icon"
								class="h-3 w-3"
							/>
						</div>
					</div>
					<span class="text-ink-gray-4 text-sm">{{ p.email }}</span>
				</div>
			</div>

			<Button
				v-if="showRemoveParticipant(p)"
				variant="ghost"
				icon="x"
				@click="$emit('removeParticipant', p.email)"
			/>
		</div>
	</div>
</template>
