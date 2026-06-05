<template>
	<!-- Circular avatar. The initials are the base layer; the image sits on top, so
	     when there's no real avatar (Gravatar 404s) the image fails to load and the
	     initials show through. Layout attrs (col, class, alignment) fall through. -->
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

import { emailFromAvatarUrl, gravatarUrl } from '@/utils/gravatar'
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

// Resolves a raw user_image to a loadable URL (or '' to fall back to initials).
// The backend hands us either an uploaded photo (/files/…) or its get_avatar
// proxy URL. For the proxy (which needs auth and returns a default image), we
// instead hit Gravatar directly with d=404 — no real avatar → 404 → initials.
// Uploaded photos / absolute URLs are resolved against the active site as-is.
function resolveSrc(image: string): string {
	if (!image) return ''
	if (image.includes('mail.api.mail.get_avatar')) {
		const email = emailFromAvatarUrl(image)
		return email ? gravatarUrl(email, 256) : ''
	}
	if (/^https?:\/\//i.test(image)) return image
	return `${site.activeSite?.url ?? ''}${image.startsWith('/') ? '' : '/'}${image}`
}

const src = computed(() => resolveSrc(props.image))
const initialsText = computed(() => initials(props.name || '?'))
const fontSize = computed(() => Math.round(props.size * 0.36))
</script>
