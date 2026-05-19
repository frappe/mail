<template>
	<div v-if="!isIframeReady" class="animate-pulse space-y-2 py-4">
		<div
			v-for="i in 5"
			:key="i"
			class="bg-surface-gray-3 h-2"
			:style="{ width: `${Math.floor(Math.random() * 40) + 60}%` }"
		/>
	</div>
	<IframeResizer
		v-show="isIframeReady"
		class="w-full"
		license="GPLv3"
		:scrolling="true"
		:srcdoc
		@on-ready="isIframeReady = true"
	/>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import iframeResizerChildScript from '@iframe-resizer/child/index.umd.js?raw'
// eslint-disable-next-line import/no-unresolved
import IframeResizer from '@iframe-resizer/vue/sfc'
import DOMPurify from 'dompurify'

import { useTheme } from '@/utils/composables'

const { content } = defineProps<{ content: string }>()

const { dataTheme } = useTheme()

const isIframeReady = ref(false)

// Listen for keyboard events from iframe
const handleMessage = (event: MessageEvent) => {
	if (event.data?.type !== 'keyboard') return

	// Create a synthetic keyboard event in the parent
	const keyboardEvent = new KeyboardEvent(event.data.eventType, {
		key: event.data.key,
		ctrlKey: event.data.ctrlKey,
		shiftKey: event.data.shiftKey,
		altKey: event.data.altKey,
		metaKey: event.data.metaKey,
		bubbles: true,
	})
	document.dispatchEvent(keyboardEvent)
}

onMounted(() => window.addEventListener('message', handleMessage))
onUnmounted(() => window.removeEventListener('message', handleMessage))

const srcdoc = computed(() => {
	const collapseButton = `
		<button
			style="
			background: ${colors.value.button};
			color: ${colors.value.text};
			padding: 0.5px 6px;
			border-radius: 8px;
			cursor: pointer;
			transition: background 0.2s;
			margin: 12px 0;
			"
			onmouseover="this.style.background='${colors.value.buttonHover}'"
			onmouseout="this.style.background='${colors.value.button}'"
			onclick="this.nextElementSibling.classList.toggle('quote-hidden');"
		>
			&middot;&middot;&middot;
		</button>
	`
	const transformedContent = DOMPurify.sanitize(content, DOMPURIFY_CONFIG)
		.replace(
			/<div\s+([^>]*)\bclass="([^"]*)"\s*([^>]*)>([\s\S]*?)<\/div>/gi,
			(match, beforeAttrs, classValue, afterAttrs, innerHtml) => {
				// Check if this div has gmail_quote or frappe_mail_quote class
				if (/\b(gmail_quote|frappe_mail_quote)\b/.test(classValue)) {
					const allAttrs = `${beforeAttrs} ${afterAttrs}`.trim()
					const attrString = allAttrs ? ` ${allAttrs}` : ''
					return `${collapseButton}<div class="quote-hidden ${classValue}"${attrString}>${innerHtml}</div>`
				}
				return match
			},
		)
		.replace(/<([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>/g, '<b>&lt;$1&gt;</b>')

	/* eslint-disable no-useless-escape */
	return `
		<!DOCTYPE html>
		<html>
		<head>
			<meta name="viewport" content="width=device-width, initial-scale=1">
			<meta name="color-scheme" content="${dataTheme.value}">
			<meta charset="UTF-8">
			<style>
				body {
					font-family: InterVar, ui-sans-serif, system-ui, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
					font-size: 14px;
					line-height: 1.25rem;
					background-color: ${colors.value.background};
					margin: 0;
				}

				blockquote {
					margin: 8px 0;
					padding-left: 12px;
					border-left: 1px solid ${colors.value.buttonHover};
				}

				table {
					color: inherit !important;
				}

				button {
					background: none;
					border: none;
					cursor: pointer;
					padding: 0;
				}

				.quote-hidden {
					display: none;
				}

				.email-pixel {
					display: none !important;
					visibility: hidden !important;
					width: 0 !important;
					height: 0 !important;
					overflow: hidden !important;
				}

				pre, code {
					font-family: 'Courier New', Courier, monospace;
					white-space: pre;
					overflow-x: auto;
				}

				@media (max-width: 640px) {
                    /* Only override specific problematic patterns */
                    table[width="600"], table[width="600px"] {
                        width: 100% !important;
                    }
                }
			</style>
			<script> ${iframeResizerChildScript} <\/script>
		</head>
		<body>
			${transformedContent}
			<script>
				// Forward keyboard events to parent
				['keydown', 'keyup', 'keypress'].forEach(eventType => {
					document.addEventListener(eventType, (e) => {
						window.parent.postMessage({
							type: 'keyboard',
							eventType: eventType,
							key: e.key,
							ctrlKey: e.ctrlKey,
							shiftKey: e.shiftKey,
							altKey: e.altKey,
							metaKey: e.metaKey,
						}, '*');
					});
				});

				// Forward link clicks to parent
				document.addEventListener('click', (e) => {
					const anchor = e.target.closest('a');
					if (anchor) {
						e.preventDefault();
						if (anchor.getAttribute('href')?.trim()) {
							window.open(anchor.href, '_blank');
						}
					}
				});
				${colors.value.script}
			<\/script>
		</body>
		</html>
	`
})

const colors = computed(() => THEME_CONFIG[dataTheme.value])

const DOMPURIFY_CONFIG = {
	ALLOWED_TAGS: [
		'html',
		'head',
		'body',
		'title',
		'meta',
		'style',
		'table',
		'tbody',
		'thead',
		'tfoot',
		'tr',
		'td',
		'th',
		'div',
		'span',
		'p',
		'br',
		'strong',
		'b',
		'em',
		'i',
		'u',
		'h1',
		'h2',
		'h3',
		'h4',
		'h5',
		'h6',
		'a',
		'img',
		'blockquote',
		'ul',
		'ol',
		'li',
		'pre',
		'code',
	],
	ALLOWED_ATTR: [
		'style',
		'class',
		'id',
		'width',
		'height',
		'align',
		'valign',
		'cellpadding',
		'cellspacing',
		'border',
		'bgcolor',
		'color',
		'href',
		'src',
		'alt',
		'title',
		'target',
		'data-type',
		'data-id',
		'data-label',
		'data-list',
		'data-email-footer',
		'xmlns',
		'content',
		'name',
		'http-equiv',
		'charset',
	],
	KEEP_CONTENT: true,
	ALLOW_UNKNOWN_PROTOCOLS: false,
	WHOLE_DOCUMENT: true,
	ADD_TAGS: ['meta', 'style', 'pre', 'code'],
	ADD_ATTR: ['cellpadding', 'cellspacing', 'border', 'bgcolor', 'xmlns', 'charset'],
	REMOVE_EMPTY: false,
}

const THEME_CONFIG = {
	light: {
		background: '#FFFFFF',
		text: '#383838',
		button: '#F3F3F3',
		buttonHover: '#EDEDED',
		script: '',
	},
	dark: {
		background: '#0F0F0F',
		text: '#D4D4D4',
		button: '#2B2B2B',
		buttonHover: '#343434',
		script: `
			function hasBackground(el) {
				while (el && el !== document.body) {
					const bg = getComputedStyle(el).backgroundColor;
					if (bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)') {
						return true;
					}
					el = el.parentElement;
				}
				return false;
			}

			function walkAndWrapTextNodes(node) {
				for (let child of Array.from(node.childNodes)) {
					if (child.nodeType === 3) {
						const trimmed = child.textContent.trim();
						if (
							trimmed.length > 0 &&
							!hasBackground(child.parentElement) &&
							child.parentElement.tagName !== 'A' &&
							child.parentElement.tagName !== 'PRE' &&
							child.parentElement.tagName !== 'CODE'
						) {
							child.parentElement.style.setProperty('color', '#D4D4D4');
						}
					} else if (child.nodeType === 1) {
						walkAndWrapTextNodes(child);
					}
				}
			}

			walkAndWrapTextNodes(document.body);
		`,
	},
}
</script>
