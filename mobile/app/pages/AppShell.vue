<template>
	<Page actionBarHidden="true">
		<StackLayout class="p-6">
			<Label
				:text="__(`You're signed in`)"
				class="text-ink-gray-9 mb-1 text-2xl font-bold"
			/>
			<Label
				:text="site.activeSite?.url || ''"
				class="text-ink-gray-5 mb-6 text-base"
				textWrap="true"
			/>
			<Button
				:text="__('Log out')"
				class="bg-surface-red-5 rounded-lg p-3 text-white"
				@tap="logout"
			/>
		</StackLayout>
	</Page>
</template>

<script setup lang="ts">
import { $navigateTo } from 'nativescript-vue'

import { loadTranslations } from '@/utils/translation'
import { sessionStore } from '@/stores/session'
import { siteStore } from '@/stores/site'
import LandingPage from '@/pages/LandingPage.vue'

const site = siteStore()
const session = sessionStore()

function logout() {
	if (!site.activeSite) return
	session.logout(site.activeSite.url)
	void loadTranslations()
	$navigateTo(LandingPage, { clearHistory: true })
}
</script>
