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
				class="fixed inset-0 z-50 flex items-center justify-center bg-black/90 text-gray-50"
				@click.self="closeViewer"
			>
				<button
					class="absolute right-4 top-4 z-10 rounded-full bg-white/10 p-2 hover:bg-white/20"
					@click="closeViewer"
				>
					<X class="h-4 w-4" />
				</button>

				<button
					:disabled="isDownloading"
					class="absolute right-16 top-4 z-10 rounded-full bg-white/10 p-2 hover:bg-white/20 disabled:opacity-50"
					@click="downloadAttachment"
				>
					<Loader v-if="isDownloading" class="h-4 w-4 animate-spin" />
					<Download v-else class="h-4 w-4" />
				</button>

				<div
					class="absolute left-1/2 top-4 z-10 flex max-w-2xl -translate-x-1/2 items-center space-x-2 rounded-full bg-white/10 px-4 py-2"
				>
					<Paperclip class="h-4 w-4" />
					<span class="truncate text-sm font-medium">
						{{ currentAttachment?.fileName }}
					</span>
				</div>

				<!-- Content area -->
				<div
					class="flex h-full w-full items-center justify-center p-4"
					@click.self="closeViewer"
				>
					<Loader v-if="isLoading" class="h-12 w-12 animate-spin" />
					<div
						v-else-if="previewUrl"
						class="flex h-full w-full items-center justify-center"
						@click.self="closeViewer"
					>
						<!-- Image Preview -->
						<img
							v-if="isImage"
							:src="previewUrl"
							:alt="currentAttachment?.fileName"
							class="max-h-full max-w-full object-contain"
						/>
						<!-- PDF Preview -->
						<iframe
							v-else-if="isPDF"
							:src="previewUrl"
							class="h-[90vh] w-full max-w-6xl rounded-lg bg-white"
							title="PDF Preview"
						/>
						<!-- Video Preview -->
						<video
							v-else-if="isVideo"
							:src="previewUrl"
							controls
							class="max-h-full max-w-full rounded-lg"
						/>
						<!-- Audio Preview -->
						<audio
							v-else-if="isAudio"
							:src="previewUrl"
							controls
							class="w-full max-w-2xl"
						/>
						<!-- Unsupported Preview -->
						<div v-else class="flex flex-col items-center justify-center space-y-4">
							<FileIcon class="h-16 w-16 text-white/60" />
							<p class="text-sm text-white/80">
								{{ __('Preview not available for this file type') }}
							</p>
							<button
								:disabled="isDownloading"
								class="flex items-center space-x-2 rounded-lg bg-white px-4 py-2 text-sm font-medium text-gray-900 hover:bg-gray-100 disabled:opacity-50"
								@click="downloadAttachment"
							>
								<Loader v-if="isDownloading" class="h-4 w-4 animate-spin" />
								<Download v-else class="h-4 w-4" />
								<span>{{ __('Download to view') }}</span>
							</button>
						</div>
					</div>
					<div v-else class="flex flex-col items-center justify-center space-y-4">
						<FileIcon class="h-16 w-16 text-white/60" />
						<p class="text-sm text-white/80">{{ __('Failed to load attachment') }}</p>
					</div>
				</div>

				<div
					v-if="attachments && attachments.length > 1"
					class="absolute bottom-4 left-1/2 z-10 flex -translate-x-1/2 items-center space-x-4 rounded-full bg-white/10 px-4 py-2 backdrop-blur-sm"
				>
					<button
						:disabled="currentIndex === 0"
						class="flex items-center space-x-1 rounded-lg px-3 py-1.5 text-sm font-medium hover:bg-white/10 disabled:opacity-50"
						@click="previousAttachment"
					>
						<ChevronLeft class="h-4 w-4" />
						<span>{{ __('Previous') }}</span>
					</button>
					<span class="text-sm text-white/80">
						{{
							__('{0} of {1}', [
								(currentIndex + 1).toString(),
								attachments.length.toString(),
							])
						}}
					</span>
					<button
						:disabled="currentIndex === attachments.length - 1"
						class="flex items-center space-x-1 rounded-lg px-3 py-1.5 text-sm font-medium hover:bg-white/10 disabled:opacity-50"
						@click="nextAttachment"
					>
						<span>{{ __('Next') }}</span>
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
	Loader,
	Paperclip,
	X,
} from 'lucide-vue-next'
import { createResource } from 'frappe-ui'

interface Attachment {
	fileName: string
	blobID: string
	type?: string
}

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

const isImage = computed(() => {
	const type = currentAttachment.value?.type || ''
	return type.startsWith('image/')
})

const isPDF = computed(() => {
	const type = currentAttachment.value?.type || ''
	return type === 'application/pdf'
})

const isVideo = computed(() => {
	const type = currentAttachment.value?.type || ''
	return type.startsWith('video/')
})

const isAudio = computed(() => {
	const type = currentAttachment.value?.type || ''
	return type.startsWith('audio/')
})

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

const loadAttachment = async () => {
	if (!currentAttachment.value?.blobID) return

	isLoading.value = true
	if (previewUrl.value) {
		URL.revokeObjectURL(previewUrl.value)
		previewUrl.value = null
	}

	await fetchAttachment.submit()
}

const fetchAttachment = createResource({
	url: 'mail.api.mail.fetch_attachment',
	makeParams: () => ({ blob_id: currentAttachment.value?.blobID }),
	onSuccess: (data: number[]) => {
		const byteArray = new Uint8Array(data)
		const blob = new Blob([byteArray], {
			type: currentAttachment.value?.type,
		})
		previewUrl.value = URL.createObjectURL(blob)
		isLoading.value = false
	},
	onError: () => (isLoading.value = false),
})

const downloadAttachment = async () => {
	if (!currentAttachment.value?.blobID) return

	isDownloading.value = true
	await downloadResource.submit()
}

const downloadResource = createResource({
	url: 'mail.api.mail.fetch_attachment',
	makeParams: () => ({ blob_id: currentAttachment.value?.blobID }),
	onSuccess: (data: number[]) => {
		const byteArray = new Uint8Array(data)
		const blob = new Blob([byteArray], {
			type: currentAttachment.value?.type,
		})
		const url = URL.createObjectURL(blob)
		const link = document.createElement('a')
		link.href = url
		link.download = currentAttachment.value?.fileName || 'attachment'
		document.body.appendChild(link)
		link.click()
		document.body.removeChild(link)
		URL.revokeObjectURL(url)
		isDownloading.value = false
	},
	onError: () => {
		isDownloading.value = false
	},
})

watch(isOpen, (newVal) => {
	if (newVal && currentAttachment.value) loadAttachment()
	else if (!newVal) closeViewer()
})

watch(currentIndex, () => {
	if (isOpen.value) loadAttachment()
})

const handleKeyDown = (event: KeyboardEvent) => {
	if (event.key === 'Escape' && isOpen.value) closeViewer()
}

onMounted(() => {
	window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
	window.removeEventListener('keydown', handleKeyDown)
})
</script>
