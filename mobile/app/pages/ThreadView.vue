<template>
	<!-- Placeholder thread detail. The real reading view (rendered messages,
	     reply/forward, attachments) is built in #489 — this just wires the
	     navigation and shows the thread's subject + sender. -->
	<Page actionBarHidden="true">
		<GridLayout rows="auto, *" class="bg-surface-white">
			<!-- top bar -->
			<GridLayout
				row="0"
				columns="auto, *, auto, auto"
				class="border-outline-gray-1 border-b px-1 py-2"
				:marginTop="safeTop"
			>
				<GridLayout col="0" class="h-10 w-10" @tap="goBack">
					<Label
						:text="lucide('chevron-left')"
						class="font-lucide text-ink-gray-7 text-2xl"
						horizontalAlignment="center"
						verticalAlignment="center"
					/>
				</GridLayout>
				<GridLayout col="2" class="h-10 w-10" @tap="() => {}">
					<Label
						:text="lucide('archive')"
						class="font-lucide text-ink-gray-6 text-xl"
						horizontalAlignment="center"
						verticalAlignment="center"
					/>
				</GridLayout>
				<GridLayout col="3" class="h-10 w-10" @tap="() => {}">
					<Label
						:text="lucide('trash-2')"
						class="font-lucide text-ink-gray-6 text-xl"
						horizontalAlignment="center"
						verticalAlignment="center"
					/>
				</GridLayout>
			</GridLayout>

			<!-- body -->
			<StackLayout row="1" class="p-5">
				<Label
					:text="thread.subject || __('[No subject]')"
					class="text-ink-gray-9 text-2xl font-bold"
					textWrap="true"
				/>
				<StackLayout orientation="horizontal" class="mt-4">
					<Label
						:text="thread.from_name || thread.from_email"
						class="text-ink-gray-8 font-semibold"
						verticalAlignment="center"
					/>
				</StackLayout>
				<Label
					:text="thread.preview || __('— No message body —')"
					class="text-ink-gray-6 mt-6 text-base"
					textWrap="true"
				/>
				<Label
					:text="__('Full thread view coming soon')"
					class="text-ink-gray-4 mt-8 text-sm"
				/>
			</StackLayout>
		</GridLayout>
	</Page>
</template>

<script setup lang="ts">
import { $navigateBack } from 'nativescript-vue'

import { lucide } from '@/utils/lucide'
import { safeAreaTop } from '@/utils/safeArea'

import type { Thread } from '@mail/types'

defineProps<{ thread: Thread }>()

const safeTop = safeAreaTop()

function goBack() {
	$navigateBack()
}
</script>
