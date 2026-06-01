<template>
	<Page actionBarHidden="true">
		<ScrollView>
			<StackLayout class="p-6">
				<Label
					:text="__('Sign in to a Frappe Mail server')"
					class="text-ink-gray-9 mb-1 text-2xl font-bold"
					textWrap="true"
				/>
				<Label
					:text="__('Enter your server URL and credentials.')"
					class="text-ink-gray-5 mb-5 text-base"
					textWrap="true"
				/>

				<Label :text="__('Server URL')" class="text-ink-gray-6 mb-1 text-sm" />
				<TextField
					v-model="siteUrl"
					hint="https://mail.example.com"
					autocapitalizationType="none"
					autocorrect="false"
					keyboardType="url"
					class="bg-surface-gray-2 text-ink-gray-9 mb-3 rounded-lg p-3"
				/>

				<Label :text="__('Email or Username')" class="text-ink-gray-6 mb-1 text-sm" />
				<TextField
					v-model="usr"
					hint="user@example.com"
					autocapitalizationType="none"
					autocorrect="false"
					keyboardType="email"
					class="bg-surface-gray-2 text-ink-gray-9 mb-3 rounded-lg p-3"
				/>

				<Label :text="__('Password')" class="text-ink-gray-6 mb-1 text-sm" />
				<TextField
					v-model="pwd"
					:secure="true"
					hint="••••••••"
					class="bg-surface-gray-2 text-ink-gray-9 mb-4 rounded-lg p-3"
				/>

				<Label
					v-if="error"
					:text="error"
					class="text-ink-red-3 mb-3 text-sm"
					textWrap="true"
				/>

				<Button
					:text="__('Sign In')"
					:isEnabled="!busy"
					class="bg-surface-blue-3 rounded-lg p-3 text-white"
					@tap="signIn"
				/>

				<ActivityIndicator v-if="busy" :busy="busy" class="mt-4" />

				<Label
					v-if="site.sites.length"
					:text="__('YOUR SITES')"
					class="text-ink-gray-5 mb-2 mt-6 text-sm font-semibold"
				/>
				<StackLayout
					v-for="s in site.sites"
					:key="s.url"
					class="bg-surface-gray-1 mb-2 rounded-lg p-4"
					@tap="useSite(s.url)"
				>
					<GridLayout columns="*, auto">
						<StackLayout col="0">
							<Label
								:text="s.app_name || s.url"
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
			</StackLayout>
		</ScrollView>
	</Page>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { loadTranslations } from '@/utils/translation'
import { sessionStore } from '@/stores/session'
import { siteStore } from '@/stores/site'

const site = siteStore()
const session = sessionStore()

const siteUrl = ref('')
const usr = ref('')
const pwd = ref('')
const busy = ref(false)
const error = ref('')

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

function useSite(url: string) {
	siteUrl.value = url
	site.setActiveSite(url)
	session.loadSession(url)
}

async function signIn() {
	error.value = ''
	if (!siteUrl.value.trim() || !usr.value.trim() || !pwd.value.trim()) {
		error.value = __('Please fill in all fields')
		return
	}
	const url = normalizeUrl(siteUrl.value)
	busy.value = true
	try {
		site.addSite({ url, app_name: url })
		site.setActiveSite(url)
		await session.login(url, usr.value, pwd.value)
		await loadTranslations()
	} catch (e) {
		error.value = messageOf(e, __('Login failed'))
	} finally {
		busy.value = false
	}
}
</script>
