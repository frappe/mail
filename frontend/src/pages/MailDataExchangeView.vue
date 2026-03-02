<template>
	<div v-if="mailExchange.data" class="flex h-screen flex-col">
		<header class="flex items-center border-b px-5 py-2.5">
			<Breadcrumbs :items="BREADCRUMBS" />
		</header>
		<div class="mx-auto my-5 rounded border p-12 sm:w-[60rem]">
			<div class="mb-4 flex items-center space-x-2">
				<h1 class="text-xl !font-semibold">{{ __('Mail Data Exchange') }}</h1>
				<Badge
					:theme="getTheme(mailExchange.data?.status)"
					:label="mailExchange.data?.status"
				/>
			</div>
			<p class="text-base">{{ operationDetails }}</p>
			<template v-if="mailExchange.data?.output">
				<hr class="my-8" />
				<h2 class="mb-4">{{ __('Output') }}</h2>
				<CopyCode :code="mailExchange.data?.output" class="max-h-80 overflow-y-auto" />
			</template>
			<template v-if="attachment.data?.file_url">
				<hr class="my-8" />
				<h2 class="mb-4">{{ __('File') }}</h2>
				<div class="flex items-center justify-between">
					<p class="text-base">
						{{
							__('{0} · {1}', [
								attachment.data?.file_type,
								formatBytes(attachment.data?.file_size),
							])
						}}
					</p>
					<Button
						icon-left="download"
						:label="__('Download')"
						@click="triggerDownload"
					/>
				</div>
			</template>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Breadcrumbs, Button, createResource } from 'frappe-ui'

import { formatBytes, getTheme } from '@/utils'
import CopyCode from '@/components/CopyCode.vue'

const { id } = defineProps<{ id: string }>()

const dayjs = inject('$dayjs')

const router = useRouter()

const mailExchange = createResource({
	url: 'frappe.client.get_value',
	auto: true,
	makeParams: () => ({
		doctype: 'Mail Exchange',
		filters: { name: id },
		fieldname: ['status', 'operation', 'started_at', 'completed_at', 'output'],
	}),
	onSuccess: (data) => {
		if (!data?.operation) router.replace('/mail-data-exchanges')
	},
	onError: () => router.replace('/mail-data-exchanges'),
})

const operationDetails = computed(() => {
	let details = mailExchange.data?.operation
	if (mailExchange.data?.started_at)
		details += __(` · Started at {0}`, [
			dayjs(mailExchange.data?.started_at).format('MMM D, YYYY h:mm A'),
		])
	if (mailExchange.data?.completed_at)
		details += __(` · Completed at {0}`, [
			dayjs(mailExchange.data?.completed_at).format('MMM D, YYYY h:mm A'),
		])
	return details
})

const attachment = createResource({
	url: 'frappe.client.get_value',
	auto: true,
	makeParams: () => ({
		doctype: 'File',
		fieldname: ['file_size', 'file_url', 'file_type', 'file_name'],
		filters: {
			attached_to_doctype: 'Mail Data Exchange',
			attached_to_name: id,
			attached_to_field: 'file',
		},
	}),
})

const triggerDownload = () => {
	const link = document.createElement('a')
	link.href = attachment.data?.file_url
	link.download = attachment.data?.file_name
	document.body.appendChild(link)
	link.click()
	document.body.removeChild(link)
}

const BREADCRUMBS = [
	{ label: __('Mail Data Exchanges'), route: '/mail-data-exchanges' },
	{ label: id },
]
</script>
