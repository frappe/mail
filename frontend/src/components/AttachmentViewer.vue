<template>
	<Teleport to="body">
		<Transition
			enter-active-class="transition-opacity duration-200"
			enter-from-class="opacity-0"
			enter-to-class="opacity-100"
			leave-active-class="transition-opacity duration-200"
			leave-from-class="opacity-100"
			leave-to-class="opacity-0"
		>
			<div
				v-if="isOpen"
				data-attachment-viewer
				class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/90 p-2 text-gray-300 sm:p-4"
				@click.self="closeViewer"
			>
				<div class="flex w-full justify-between">
					<div class="flex max-w-2xl items-center space-x-2 truncate rounded">
						<Paperclip class="h-4 w-4" />
						<span class="truncate text-base font-medium">
							{{ currentAttachment?.filename }}
						</span>
					</div>
					<div class="shrink-0 space-x-2 sm:space-x-4">
						<button
							:disabled="isDownloading"
							class="rounded p-1.5 hover:bg-white/20 disabled:opacity-50"
							@click="downloadAttachment"
						>
							<Download class="h-4 w-4" />
						</button>
						<button class="rounded p-1.5 hover:bg-white/20" @click="closeViewer">
							<X class="h-4 w-4" />
						</button>
					</div>
				</div>

				<!-- Content area -->
				<div
					class="flex h-full w-full items-center justify-center"
					@click.self="closeViewer"
				>
					<LoaderCircle v-if="isLoading" class="h-8 w-8 animate-spin" />
					<div
						v-else-if="previewUrl"
						class="flex h-full w-full items-center justify-center"
						@click.self="closeViewer"
					>
						<!-- Image Preview -->
						<img
							v-if="isImage"
							:src="previewUrl"
							:alt="currentAttachment?.filename"
							class="max-h-[85vh] max-w-full object-contain"
						/>
						<!-- PDF Preview -->
						<iframe
							v-else-if="isPDF"
							:src="previewUrl"
							:title="__('PDF Preview')"
							class="h-[85vh] w-full max-w-6xl"
						/>
						<!-- Video Preview -->
						<video
							v-else-if="isVideo"
							:src="previewUrl"
							:title="__('Video Preview')"
							controls
							class="max-h-[85vh] max-w-full"
						/>
						<!-- Audio Preview -->
						<audio
							v-else-if="isAudio"
							:src="previewUrl"
							:title="__('Audio Preview')"
							controls
							class="w-full max-w-2xl"
						/>
						<!-- Unsupported Preview -->
						<div v-else class="flex flex-col items-center justify-center space-y-4">
							<FileIcon class="h-16 w-16" />
							<p class="text-sm">
								{{ __('Preview not available for this file type') }}
							</p>
							<Button
								:label="__('Download')"
								:icon-left="Download"
								:disabled="isDownloading"
								@click="downloadAttachment"
							/>
						</div>
					</div>
					<div v-else class="flex flex-col items-center justify-center space-y-4">
						<FileIcon class="h-16 w-16" />
						<p class="text-sm">{{ __('Failed to load attachment') }}</p>
					</div>
				</div>

				<div
					v-if="attachments && attachments.length > 1"
					class="flex items-center max-sm:w-full max-sm:justify-between sm:space-x-4"
				>
					<button
						:disabled="currentIndex === 0"
						class="rounded p-1.5 disabled:opacity-50"
						:class="{ 'hover:bg-white/20': currentIndex !== 0 }"
						@click="previousAttachment"
					>
						<ChevronLeft class="h-4 w-4" />
					</button>
					<span class="text-sm">
						{{
							__('{0} of {1}', [
								(currentIndex + 1).toString(),
								attachments.length.toString(),
							])
						}}
					</span>
					<button
						:disabled="currentIndex === attachments.length - 1"
						class="rounded p-1.5 disabled:opacity-50"
						:class="{ 'hover:bg-white/20': currentIndex !== attachments.length - 1 }"
						@click="nextAttachment"
					>
						<ChevronRight class="h-4 w-4" />
					</button>
				</div>
			</div>
		</Transition>
	</Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
	ChevronLeft,
	ChevronRight,
	Download,
	FileIcon,
	LoaderCircle,
	Paperclip,
	X,
} from 'lucide-vue-next'
import { Button, createResource } from 'frappe-ui'

import { raiseToast } from '@/utils'

import type { Attachment } from '@/types'

const { attachments, initialIndex } = defineProps<{
	attachments?: Attachment[]
	initialIndex?: number
}>()

const isOpen = defineModel<boolean>()
const currentIndex = ref(initialIndex || 0)
const isLoading = ref(false)
const isDownloading = ref(false)
const previewUrl = ref<string | null>(null)

const currentAttachment = computed(() => attachments?.[currentIndex.value])
const isImage = computed(() => currentAttachment.value?.type?.startsWith('image/'))
const isPDF = computed(() => currentAttachment.value?.type === 'application/pdf')
const isVideo = computed(() => currentAttachment.value?.type?.startsWith('video/'))
const isAudio = computed(() => currentAttachment.value?.type?.startsWith('audio/'))

const closeViewer = () => {
	isOpen.value = false
	if (previewUrl.value) {
		URL.revokeObjectURL(previewUrl.value)
		previewUrl.value = null
	}
}

const previousAttachment = () => {
	if (currentIndex.value > 0) currentIndex.value--
}

const nextAttachment = () => {
	if (attachments && currentIndex.value < attachments.length - 1) currentIndex.value++
}

const loadAttachment = () => {
	if (!currentAttachment.value?.blob_id) return

	isLoading.value = true
	if (previewUrl.value) {
		URL.revokeObjectURL(previewUrl.value)
		previewUrl.value = null
	}

	fetchAttachment.submit()
}

const fetchAttachment = createResource({
	url: 'mail.api.mail.fetch_attachment',
	makeParams: () => ({ blob_id: currentAttachment.value?.blob_id }),
	onSuccess: (data: number[]) => {
		const byteArray = new Uint8Array(data)
		const blob = new Blob([byteArray], { type: currentAttachment.value?.type })
		previewUrl.value = URL.createObjectURL(blob)
		isLoading.value = false
	},
	onError: (error) => {
		isLoading.value = false
		raiseToast(error.message, 'error')
	},
	cache: ['attachment', currentAttachment.value?.blob_id],
})

const downloadAttachment = () => {
	if (!currentAttachment.value?.blob_id || !previewUrl.value) return

	isDownloading.value = true
	const link = document.createElement('a')
	link.href = previewUrl.value
	link.download = currentAttachment.value?.filename || 'attachment'
	document.body.appendChild(link)
	link.click()
	document.body.removeChild(link)
	isDownloading.value = false
}

watch(isOpen, (newVal) => {
	currentIndex.value = initialIndex || 0
	if (newVal && currentAttachment.value) loadAttachment()
	else if (!newVal) closeViewer()
})

watch(currentIndex, () => {
	if (isOpen.value) loadAttachment()
})

const handleKeyDown = (event: KeyboardEvent) => {
	if (event.key === 'Escape' && isOpen.value) closeViewer()
}

onMounted(() => window.addEventListener('keydown', handleKeyDown))
onUnmounted(() => window.removeEventListener('keydown', handleKeyDown))
</script>
