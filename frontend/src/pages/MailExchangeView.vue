<template>
	<div v-if="mailExchange.data" class="flex h-screen flex-col">
		<header class="flex items-center justify-between border-b px-5 py-2.5">
			<Breadcrumbs :items="BREADCRUMBS" />
			<Dropdown
				v-if="user.data.is_system_manager"
				:options="dropdownOptions"
				:button="{ icon: 'more-horizontal' }"
			/>
		</header>
		<div class="mx-auto my-5 rounded border p-12 sm:w-[60rem]">
			<div class="flex items-center space-x-2">
				<h1 class="text-xl !font-semibold">
					{{ __('Mail {0}', [__(mailExchange.data?.operation)]) }}
				</h1>
				<Badge
					:theme="getTheme(mailExchange.data?.status)"
					:label="mailExchange.data?.status"
				/>
			</div>
			<p class="my-4 text-base">{{ operationDetails }}</p>
			<template v-if="mailExchange.data?.output">
				<hr class="my-8" />
				<h2 class="mb-4">{{ __('Output') }}</h2>
				<CopyCode :code="mailExchange.data?.output" class="max-h-80 overflow-y-auto" />
			</template>
			<template v-if="attachment.data?.file_url">
				<h2 class="mb-4 mt-8">{{ __('File') }}</h2>
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
import { Badge, Breadcrumbs, Button, Dropdown, createResource } from 'frappe-ui'

import { formatBytes, getTheme } from '@/utils'
import CopyCode from '@/components/CopyCode.vue'

const { id } = defineProps<{ id: string }>()

const user = inject('$user')
const dayjs = inject('$dayjs')

const router = useRouter()

const mailExchange = createResource({
	url: 'frappe.client.get_value',
	auto: true,
	makeParams: () => ({
		doctype: 'Mail Exchange',
		filters: { name: id },
		fieldname: [
			'status',
			'operation',
			'started_at',
			'completed_at',
			'output',
			'import_format',
			'export_format',
		],
	}),
	onSuccess: (data) => {
		if (!data?.operation) router.replace('/mail-exchanges')
	},
	onError: () => router.replace('/mail-exchanges'),
})

const operationDetails = computed(() => {
	const format = mailExchange.data?.import_format || mailExchange.data?.export_format
	return `${format.toUpperCase()} · ${dayjs(mailExchange.data?.started_at).format('MMM D, YYYY [at] h:mm A')}`
})

const attachment = createResource({
	url: 'frappe.client.get_value',
	auto: true,
	makeParams: () => ({
		doctype: 'File',
		fieldname: ['file_size', 'file_url', 'file_type', 'file_name'],
		filters: {
			attached_to_doctype: 'Mail Exchange',
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

const dropdownOptions = computed(() => [
	{
		label: __('View in Desk'),
		icon: 'external-link',
		onClick: () => window.open(`/app/mail-exchange/${id}`, '_blank')?.focus(),
	},
])

const BREADCRUMBS = [{ label: __('Mail Exchanges'), route: '/mail-exchanges' }, { label: id }]
</script>
