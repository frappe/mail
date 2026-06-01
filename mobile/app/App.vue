<template>
	<Frame>
		<AppShell v-if="session.isLoggedIn" />
		<LandingPage v-else />
	</Frame>
</template>

<script setup lang="ts">
import { sessionStore } from '@/stores/session'
import AppShell from '@/pages/AppShell.vue'
import LandingPage from '@/pages/LandingPage.vue'

const session = sessionStore()
</script>
