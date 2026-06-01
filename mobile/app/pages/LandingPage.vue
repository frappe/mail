<template>
	<Page>
		<ActionBar title="Frappe Mail" />
		<ScrollView>
			<StackLayout class="p-6">
				<Label
					text="Sign in to a Frappe Mail server"
					class="text-ink-gray-9 mb-1 text-2xl font-bold"
					textWrap="true"
				/>
				<Label
					text="Enter your server URL to get started."
					class="text-ink-gray-5 mb-5 text-base"
					textWrap="true"
				/>

				<!-- Add site -->
				<GridLayout columns="*, auto" class="mb-2">
					<TextField
						v-model="siteInput"
						col="0"
						hint="https://mail.example.com"
						autocapitalizationType="none"
						autocorrect="false"
						keyboardType="url"
						class="bg-surface-gray-2 text-ink-gray-9 rounded-lg p-3"
						@returnPress="addSite"
					/>
					<Button
						col="1"
						text="Add"
						:isEnabled="!busy"
						class="bg-surface-blue-3 ml-2 rounded-lg px-4 text-white"
						@tap="addSite"
					/>
				</GridLayout>
				<Label
					v-if="error"
					:text="error"
					class="text-ink-red-3 mb-2 text-sm"
					textWrap="true"
				/>

				<!-- Saved sites -->
				<Label
					v-if="site.sites.length"
					text="YOUR SITES"
					class="text-ink-gray-5 mb-2 mt-5 text-sm font-semibold"
				/>
				<StackLayout
					v-for="s in site.sites"
					:key="s.url"
					class="bg-surface-gray-1 mb-2 rounded-lg p-4"
					@tap="selectAndLogin(s.url, s.client_id)"
				>
					<GridLayout columns="*, auto">
						<StackLayout col="0">
							<Label
								:text="s.app_name || s.sitename"
								class="text-ink-gray-9 text-base font-semibold"
							/>
							<Label :text="s.url" class="text-ink-gray-5 text-sm" textWrap="true" />
						</StackLayout>
						<Label
							col="1"
							text="✕"
							class="text-ink-gray-4 p-2"
							@tap="site.removeSite(s.url)"
						/>
					</GridLayout>
				</StackLayout>

				<ActivityIndicator v-if="busy" :busy="busy" class="mt-4" />
			</StackLayout>
		</ScrollView>
	</Page>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { useApi } from '@/utils/api'
import { sessionStore } from '@/stores/session'
import { siteStore } from '@/stores/site'

import type { SiteInfo } from '@mail/types'

const site = siteStore()
const session = sessionStore()
const { unauthenticatedCall } = useApi()

const siteInput = ref('')
const busy = ref(false)
const error = ref('')

// Discovery payload returned by mail.api.mobile.get_client_id.
type ClientInfo = { client_id: string; app_name: string; logo: string; sitename: string }

function normalizeUrl(input: string): string {
	let url = input.trim().replace(/\/+$/, '')
	if (!/^https?:\/\//.test(url)) url = `https://${url}`
	return url
}

function messageOf(e: unknown, fallback: string): string {
	return e && typeof e === 'object' && 'message' in e
		? String((e as { message: unknown }).message)
		: fallback
}

async function addSite() {
	error.value = ''
	if (!siteInput.value.trim()) return
	const url = normalizeUrl(siteInput.value)
	busy.value = true
	try {
		const info = await unauthenticatedCall<ClientInfo>(url, 'mail.api.mobile.get_client_id')
		const siteInfo: SiteInfo = {
			url,
			sitename: info.sitename,
			client_id: info.client_id,
			app_name: info.app_name,
			logo: info.logo,
		}
		site.addSite(siteInfo)
		siteInput.value = ''
		await selectAndLogin(url, info.client_id)
	} catch (e) {
		error.value = messageOf(e, 'Could not reach that server')
	} finally {
		busy.value = false
	}
}

async function selectAndLogin(url: string, clientId: string) {
	error.value = ''
	site.setActiveSite(url)
	busy.value = true
	try {
		await session.login(url, clientId)
	} catch (e) {
		error.value = messageOf(e, 'Login failed')
	} finally {
		busy.value = false
	}
}
</script>
