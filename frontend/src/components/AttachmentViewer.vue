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
				v-if="show"
				data-attachment-viewer
				class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/90 p-2 text-gray-300 sm:p-4"
				@click.self="closeViewer"
			>
				<div class="flex w-full justify-between">
					<div class="flex max-w-2xl items-center space-x-2 truncate rounded">
						<component
							:is="getFileIcon(currentAttachment?.type)"
							class="h-4 w-4 shrink-0"
						/>
						<span class="truncate text-base font-medium">
							{{ currentAttachment?.filename }}
						</span>
					</div>
					<div class="shrink-0 space-x-2 sm:space-x-4">
						<button
							v-if="previewUrl && !fetchAttachment.loading && canPrint"
							class="rounded p-1.5 hover:bg-white/20"
							@click="printAttachment"
						>
							<Printer class="h-4 w-4" />
						</button>
						<button
							v-if="previewUrl && !fetchAttachment.loading"
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
					<LoaderCircle v-if="fetchAttachment.loading" class="h-8 w-8 animate-spin" />
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
						<template v-else-if="isPDF">
							<VuePdfEmbed
								v-if="isMobile"
								annotation-layer
								text-layer
								:source="previewUrl"
								class="h-[85vh] w-full max-w-6xl space-y-2 overflow-auto"
							/>
							<embed
								v-else
								:src="previewUrl"
								type="application/pdf"
								class="h-[85vh] w-full max-w-6xl"
							/>
						</template>

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
import 'vue-pdf-embed/dist/styles/annotationLayer.css'
import 'vue-pdf-embed/dist/styles/textLayer.css'

import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import VuePdfEmbed from 'vue-pdf-embed'
import {
	ChevronLeft,
	ChevronRight,
	Download,
	FileIcon,
	LoaderCircle,
	Printer,
	X,
} from 'lucide-vue-next'
import { Button } from 'frappe-ui'

import { fetchAttachment, getAttachmentUrl } from '@/resources'
import { getFileIcon } from '@/utils'
import { useScreenSize } from '@/utils/composables'

import type { Attachment } from '@/types'

const { attachments, initialIndex } = defineProps<{
	attachments?: Attachment[]
	initialIndex?: number
}>()

const { isMobile } = useScreenSize()

const show = defineModel<boolean>()
const currentIndex = ref(initialIndex || 0)
const isDownloading = ref(false)
const previewUrl = ref<string | null>(null)

const currentAttachment = computed(() => attachments?.[currentIndex.value])
const isImage = computed(() => currentAttachment.value?.type?.startsWith('image/'))
const isPDF = computed(() => currentAttachment.value?.type === 'application/pdf')
const isVideo = computed(() => currentAttachment.value?.type?.startsWith('video/'))
const isAudio = computed(() => currentAttachment.value?.type?.startsWith('audio/'))
const canPrint = computed(() => isImage.value || isPDF.value)

const closeViewer = () => {
	show.value = false
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

const loadAttachment = async () => {
	if (!currentAttachment.value?.blob_id) return

	if (previewUrl.value) {
		URL.revokeObjectURL(previewUrl.value)
		previewUrl.value = null
	}

	previewUrl.value = await getAttachmentUrl(
		currentAttachment.value.blob_id,
		currentAttachment.value.type,
	)
}

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

const printAttachment = () => {
	if (!previewUrl.value || !canPrint.value) return

	const iframe = document.createElement('iframe')
	iframe.style.position = 'fixed'
	iframe.style.right = '0'
	iframe.style.bottom = '0'
	iframe.style.width = '0'
	iframe.style.height = '0'
	iframe.style.border = 'none'
	document.body.appendChild(iframe)

	const iframeDoc = iframe.contentWindow?.document
	if (!iframeDoc) return document.body.removeChild(iframe)

	if (isPDF.value) {
		iframe.style.width = '100%'
		iframe.style.height = '100%'
		iframe.src = previewUrl.value
		iframe.onload = () => {
			iframe.contentWindow?.print()
			setTimeout(() => document.body.removeChild(iframe), 1000)
		}
		return
	}

	iframe.srcdoc = `
			<html>
				<head>
					<title>${currentAttachment.value?.filename || 'Print'}</title>
					<style>
						body { margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
						img { max-width: 100%; height: auto; }
						@media print { body { margin: 0; } img { max-width: 100%; height: auto; } }
					</style>
				</head>
				<body>
					<img src="${previewUrl.value}" />
				</body>
			</html>
		`

	iframe.onload = () => {
		iframe.contentWindow?.print()
		setTimeout(() => document.body.removeChild(iframe), 1000)
	}
}

watch(show, (val) => {
	if (!val) return

	if (currentIndex.value === initialIndex) loadAttachment()
	else currentIndex.value = initialIndex || 0
})

watch(currentIndex, () => {
	if (show.value) loadAttachment()
})

const handleKeyDown = (event: KeyboardEvent) => {
	if (!show.value) return

	if (event.key === 'ArrowLeft') return previousAttachment()
	if (event.key === 'ArrowRight') return nextAttachment()
	if (event.key === 'Escape') return closeViewer()
}

onMounted(() => window.addEventListener('keydown', handleKeyDown))
onUnmounted(() => window.removeEventListener('keydown', handleKeyDown))
</script>
