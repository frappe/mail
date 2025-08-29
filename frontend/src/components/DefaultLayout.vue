<template>
	<div v-if="userResource?.data?.name" class="relative flex h-full flex-col">
		<div class="h-full flex-1">
			<div class="isolate flex h-screen text-base">
				<AppSidebar v-if="isMobile" />
				<div
					v-else
					class="relative block min-h-0 flex-shrink-0 overflow-hidden hover:overflow-auto"
				>
					<AppSidebar />
				</div>
				<div id="scrollContainer" class="w-full overflow-auto">
					<slot />
				</div>
			</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import { useScreenSize } from '@/utils/composables'
import { userStore } from '@/stores/user'
import AppSidebar from '@/components/AppSidebar.vue'

const { userResource } = userStore()

const { isMobile } = useScreenSize()
</script>
