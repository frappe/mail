<template>
	<!-- Circular avatar: sender/account image when available, else monochrome
	     initials. Layout attrs (col, class, alignment) fall through to the root. -->
	<GridLayout class="bg-surface-gray-2 rounded-full" :width="size" :height="size">
		<Image
			v-if="src"
			:src="src"
			stretch="aspectFill"
			class="rounded-full"
			:width="size"
			:height="size"
		/>
		<Label
			v-else
			:text="initialsText"
			:fontSize="fontSize"
			class="text-ink-gray-6 font-semibold"
			horizontalAlignment="center"
			verticalAlignment="center"
		/>
	</GridLayout>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { siteStore } from '@/stores/site'

const props = withDefaults(defineProps<{ name: string; image?: string; size?: number }>(), {
	image: '',
	size: 44,
})

const site = siteStore()

// First two initials of a name (or the first two letters of a single word),
// falling back to '?'. Avoids Unicode property escapes (\p{…}) — the Android
// JS engine's regex doesn't support them.
function initials(name: string): string {
	const parts = name.trim().split(/\s+/).filter(Boolean)
	if (parts.length === 0) return '?'
	if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
	return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

// Resolves a raw user_image to an absolute, loadable URL, or '' to fall back to
// initials. The backend's get_avatar API URL (gravatar / identicon — no file
// extension, needs auth) is intentionally skipped: an <Image> can't carry the
// OAuth bearer token, and the monochrome initials are the design default.
// Real uploaded photos (/files/…) are resolved against the active site.
function resolveSrc(image: string): string {
	if (!image || !/\.(png|jpe?g|gif|webp)$/i.test(image)) return ''
	if (/^https?:\/\//i.test(image)) return image
	return `${site.activeSite?.url ?? ''}${image.startsWith('/') ? '' : '/'}${image}`
}

const src = computed(() => resolveSrc(props.image))
const initialsText = computed(() => initials(props.name || '?'))
const fontSize = computed(() => Math.round(props.size * 0.36))
</script>
