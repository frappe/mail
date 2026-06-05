<template>
	<!-- Circular avatar. The initials are the base layer; the image sits on top, so
	     when there's no real avatar (get_avatar returns 404 in strict mode) the image
	     fails to load and the initials show through. Layout attrs (col, class,
	     alignment) fall through to the root. -->
	<GridLayout class="bg-surface-gray-2 rounded-full" :width="size" :height="size">
		<Label
			:text="initialsText"
			:fontSize="fontSize"
			class="text-ink-gray-6 font-semibold"
			horizontalAlignment="center"
			verticalAlignment="center"
		/>
		<Image
			v-if="src"
			:src="src"
			stretch="aspectFill"
			class="rounded-full"
			:width="size"
			:height="size"
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

// Resolves a raw user_image to an absolute, loadable URL (or '' to fall back to
// initials). Relative URLs — the get_avatar API endpoint or an uploaded /files
// photo — are resolved against the active site. get_avatar is guest-accessible
// (see mail.api.mail.get_avatar) so the <Image> loads without the bearer token.
// For the gravatar proxy we add strict=1 so a missing avatar 404s (→ initials)
// rather than returning a default identicon.
function resolveSrc(image: string): string {
	if (!image) return ''
	const abs = /^https?:\/\//i.test(image)
		? image
		: `${site.activeSite?.url ?? ''}${image.startsWith('/') ? '' : '/'}${image}`
	if (abs.includes('mail.api.mail.get_avatar')) {
		return `${abs}${abs.includes('?') ? '&' : '?'}strict=1`
	}
	return abs
}

const src = computed(() => resolveSrc(props.image))
const initialsText = computed(() => initials(props.name || '?'))
const fontSize = computed(() => Math.round(props.size * 0.36))
</script>
