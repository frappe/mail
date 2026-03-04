<template>
	<div v-if="mailExchange.data" class="flex h-screen flex-col">
		<header class="flex items-center justify-between border-b px-5 py-2.5">
			<Breadcrumbs :items="breadcrumbs" />
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
			<CopyCode
				v-if="mailExchange.data?.output"
				:code="mailExchange.data?.output"
				class="mt-8 max-h-80 overflow-y-auto"
			/>
			<template v-if="attachment.data?.file_url">
				<hr class="my-8" />
				<a
					v-if="attachment.data?.file_url"
					class="flex cursor-pointer items-center space-x-2 text-base hover:underline"
					:href="attachment.data.file_url"
					target="_blank"
				>
					<Download class="text-ink-gray-4 h-4 w-4 shrink-0" />
					<span>
						{{
							__('{0} ({1})', [
								attachment.data?.file_name,
								formatBytes(attachment.data?.file_size),
							])
						}}
					</span>
				</a>
			</template>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import { Download } from 'lucide-vue-next'
import { Badge, Breadcrumbs, Dropdown, createResource } from 'frappe-ui'

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

const dropdownOptions = computed(() => [
	{
		label: __('View in Desk'),
		icon: 'external-link',
		onClick: () => window.open(`/app/mail-exchange/${id}`, '_blank')?.focus(),
	},
])

const breadcrumbs = computed(() => [
	{
		label: __('Mail Exchanges'),
		route: `/mail-exchanges?operation=${mailExchange.data?.operation}`,
	},
	{ label: id },
])
</script>
