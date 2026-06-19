<script setup lang="ts">
import { computed } from 'vue'

import { isEmail } from '@/utils'

// Matches URLs (http/https/www) and email addresses in plain text.
const URL_OR_EMAIL_REGEX =
	/(https?:\/\/[^\s<]+|www\.[^\s<]+|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/gi
// Trailing punctuation unlikely to be part of the link.
const TRAILING_PUNCTUATION = /[.,;:!?)\]}'"]+$/

interface Segment {
	text: string
	href?: string
}

const props = defineProps<{ text?: string | null }>()

// Splits the text into plain runs and link runs. Rendered as <span>/<a> elements with the text in
// {{ }} (auto-escaped), so the body can never be interpreted as markup — for rich HTML bodies use
// <EmailContent> (DOMPurify) instead.
const segments = computed<Segment[]>(() => {
	const text = props.text ?? ''
	const result: Segment[] = []
	let lastIndex = 0

	for (const match of text.matchAll(URL_OR_EMAIL_REGEX)) {
		const token = match[0]
		const start = match.index ?? 0

		const before = text.slice(lastIndex, start)
		if (before) result.push({ text: before })

		const trailing = token.match(TRAILING_PUNCTUATION)?.[0] ?? ''
		const link = token.slice(0, token.length - trailing.length)
		const href = isEmail(link)
			? `mailto:${link}`
			: link.startsWith('www.')
				? `https://${link}`
				: link

		result.push({ text: link, href })
		if (trailing) result.push({ text: trailing })

		lastIndex = start + token.length
	}

	const rest = text.slice(lastIndex)
	if (rest) result.push({ text: rest })

	return result
})
</script>

<template>
	<div class="whitespace-pre-wrap break-words pt-4 font-sans text-base !leading-5 sm:text-sm">
		<template v-for="(segment, index) in segments" :key="index">
			<a
				v-if="segment.href"
				:href="segment.href"
				target="_blank"
				rel="noopener noreferrer"
				class="text-ink-blue-2 hover:underline"
				>{{ segment.text }}</a
			>
			<span v-else>{{ segment.text }}</span>
		</template>
	</div>
</template>
