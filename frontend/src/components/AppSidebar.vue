<template>
	<div
		class="flex h-full flex-col justify-between transition-all duration-300 ease-in-out bg-gray-100"
		:class="isSidebarCollapsed ? 'w-14' : 'w-56'"
	>
		<div
			class="flex flex-col overflow-hidden"
			:class="isSidebarCollapsed ? 'items-center' : ''"
		>
			<UserDropdown class="p-2" :isCollapsed="isSidebarCollapsed" />
			<div class="flex flex-col overflow-y-auto">
				<SidebarLink
					v-for="link in sidebarLinks"
					:link="link"
					:isCollapsed="isSidebarCollapsed"
					class="mx-2 my-0.5"
				/>
			</div>
		</div>
		<SidebarLink
			:link="{
				label: isSidebarCollapsed ? 'Expand' : 'Collapse',
			}"
			:isCollapsed="isSidebarCollapsed"
			@click="isSidebarCollapsed = !isSidebarCollapsed"
			class="m-2"
		>
			<template #icon>
				<span class="grid h-5 w-6 flex-shrink-0 place-items-center">
                    <ArrowLeftFromLine class="h-4 w-4 text-gray-700 duration-300 ease-in-out" :class="{
                        '[transform:rotateY(180deg)]': isSidebarCollapsed
                    }" />
				</span>
			</template>
		</SidebarLink>
	</div>
</template>

<script setup>
import UserDropdown from '@/components/UserDropdown.vue'
import SidebarLink from '@/components/SidebarLink.vue'
import { useStorage } from '@vueuse/core'
import { ref, computed } from 'vue'
import { ArrowLeftFromLine } from 'lucide-vue-next'
import { getSidebarLinks } from '../utils'

const sidebarLinks = computed(() => getSidebarLinks())

const getSidebarFromStorage = () => {
	return useStorage('sidebar_is_collapsed', false)
}

let isSidebarCollapsed = ref(getSidebarFromStorage())
</script>
