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
import { computed, ref } from 'vue'
// eslint-disable-next-line import/no-unresolved
import IframeResizer from '@iframe-resizer/vue/sfc'
import DOMPurify from 'dompurify'

import { useTheme } from '@/utils/composables'

const { content } = defineProps<{ content: string }>()

const { activeTheme } = useTheme()

const isIframeReady = ref(false)

const srcdoc = computed(() => {
	const collapseButton = `
		<button
			style="
			background: ${colors.value.button};
			color: ${colors.value.text};
			padding: 0.5px 6px;
			border-radius: 4px;
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
			/<div\s+class="(gmail_quote|frappe_mail_quote)"([^>]*)>([\s\S]*?)<\/div>/gi,
			(_, quoteClass, otherAttrs, innerHtml) =>
				`${collapseButton}<div class="quote-hidden ${quoteClass}"${otherAttrs}>${innerHtml}</div>`,
		)
		.replace(/<([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>/g, '<b>&lt;$1&gt;</b>')

	/* eslint-disable no-useless-escape */
	return `
		<!DOCTYPE html>
		<html>
		<head>
			<meta name="viewport" content="width=device-width, initial-scale=1">
			<meta name="color-scheme" content="${activeTheme.value}">
			<style>
				body {
					font-family: InterVar, ui-sans-serif, system-ui, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
					font-size: 14px;
					line-height: 1.25rem;
					background-color: ${colors.value.background};
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

				@media (max-width: 640px) {
                    /* Only override specific problematic patterns */
                    table[width="600"], table[width="600px"] {
                        width: 100% !important;
                    }
                }
			</style>
			<script
			src="https://cdn.jsdelivr.net/npm/@iframe-resizer/child@5.4.6"
			type="text/javascript"
			><\/script>
		</head>
		<body>
			${transformedContent}
			<script>
				document.addEventListener('click', (e) => {
					if (e.target.tagName === 'A') {
						e.preventDefault();
						window.open(e.target.href, '_blank');
					}
				});
				${colors.value.script}
			<\/script>
		</body>
		</html>
	`
})

const colors = computed(() => THEME_CONFIG[activeTheme.value])

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
	ADD_TAGS: ['meta', 'style'],
	ADD_ATTR: ['cellpadding', 'cellspacing', 'border', 'bgcolor', 'xmlns'],
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
							child.parentElement.tagName !== 'A'
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
