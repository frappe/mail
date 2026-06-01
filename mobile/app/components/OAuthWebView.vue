<template>
	<Page>
		<GridLayout rows="auto, *" class="bg-surface-white">
			<GridLayout row="0" columns="*, auto" class="px-4 py-3">
				<Label
					col="0"
					:text="__('Sign in')"
					verticalAlignment="center"
					class="text-ink-gray-9 text-lg font-semibold"
				/>
				<Button col="1" :text="__('Cancel')" class="text-ink-blue-3" @tap="cancel" />
			</GridLayout>
			<WebView row="1" :src="authorizeUrl" @loadStarted="onLoad" @loadFinished="onLoad" />
		</GridLayout>
	</Page>
</template>

<script setup lang="ts">
import { $closeModal } from 'nativescript-vue'

import { REDIRECT_URI, type RedirectResult } from '@/utils/oauth'

import type { LoadEventData } from '@nativescript/core'

defineProps<{ authorizeUrl: string }>()

// Guard so the first matching navigation wins (loadStarted + loadFinished both fire).
let settled = false

function onLoad(args: LoadEventData) {
	const url = args.url || ''
	if (settled || !url.startsWith(REDIRECT_URI)) return
	settled = true
	$closeModal(parseRedirect(url))
}

function parseRedirect(url: string): RedirectResult {
	const query = url.split('?')[1] || ''
	const params: Record<string, string> = {}
	for (const pair of query.split('&')) {
		const [k, v] = pair.split('=')
		if (k) params[decodeURIComponent(k)] = decodeURIComponent(v || '')
	}
	return { code: params.code, state: params.state, error: params.error }
}

function cancel() {
	if (settled) return
	settled = true
	$closeModal(null)
}
</script>
