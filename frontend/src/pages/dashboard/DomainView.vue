<template>
	<DashboardLayout
		v-if="domain?.data"
		:breadcrumbs="BREADCRUMBS"
		:badge-label="badge.label"
		:badge-theme="badge.theme"
	>
		<template #actions>
			<Dropdown :options="dropdownOptions" :button="{ icon: 'more-horizontal' }" />
		</template>
		<template #default>
			<div class="bg-surface-blue-1 rounded-md border">
				<div class="space-y-2 p-4">
					<h3 class="font-medium">{{ BANNER.title }}</h3>
					<p class="text-ink-gray-5 text-sm">{{ BANNER.message }}</p>
				</div>
			</div>
			<div class="rounded-md border">
				<h2 class="p-4">{{ __('DNS Records') }}</h2>
				<DNSRecords
					:title="__('Email Deliverability')"
					:description="
						__('Email authentication records that protect your domain from spoofing.')
					"
					:records="emailDeliverabilityRecords"
					:badge-label="__('Required')"
					badge-theme="red"
				/>
				<DNSRecords
					:title="__('Inbound Mail Routing')"
					:description="
						__(
							'Mail routing records that ensure messages sent to your domain are delivered to the correct mail server.',
						)
					"
					:records="inboundMailRoutingRecords"
					:badge-label="__('Recommended')"
					badge-theme="orange"
				/>
				<DNSRecords
					:title="__('Service Configuration Records')"
					:description="
						__(
							'Service records that enable automatic mail setup and enforce secure transport for your domain.',
						)
					"
					:records="serviceConfigurationRecords"
				/>
				<DNSRecords
					:title="__('Service Discovery Records')"
					:description="
						__(
							'Records that allow mail and sync apps to automatically locate and connect to your domain’s email, calendar, and contacts services.',
						)
					"
					:records="serviceDiscoveryRecords"
				/>
				<DNSRecords
					:title="__('Email Transport Security Records')"
					:description="
						__(
							'TXT records that enforce encrypted mail delivery and provide reporting on failed or insecure SMTP connections.',
						)
					"
					:records="transportSecurityRecords"
				/>
			</div>
		</template>
	</DashboardLayout>
	<Dialog v-model="showConfirmDialog" :options="confirmDialogOptions" />
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Dialog, Dropdown, createResource, usePageMeta } from 'frappe-ui'

import { raiseToast } from '@/utils'
import DNSRecords from '@/components/DNSRecords.vue'
import DashboardLayout from '@/components/DashboardLayout.vue'

type DNSRecord = Record<string, string>

type DomainData = {
	id: string
	name: string
	description: string
	is_enabled: boolean
	created_at: string
	dns_records: DNSRecord[]
}

type ResourceError = {
	messages?: string[]
	message?: string
}

const getErrorMessage = (error: ResourceError) =>
	error.messages?.[0] || error.message || __('Request failed.')

const { domainId } = defineProps<{ domainId: string }>()

usePageMeta(() => ({ title: domain.data?.name || domainId }))

const router = useRouter()

const showConfirmDialog = ref(false)

const domain = createResource({
	url: 'mail.api.admin.get_domain',
	auto: true,
	makeParams: () => ({ domain_id: domainId }),
	cache: ['mailDomain', domainId],
	onError: () => router.replace({ name: 'Domains' }),
})

const domainRecords = computed<DNSRecord[]>(
	() => (domain.data as DomainData | undefined)?.dns_records || [],
)

const emailDeliverabilityRecords = computed(() =>
	domainRecords.value.filter(
		(record) =>
			record.type === 'TXT' &&
			!(record.name.startsWith('_smtp') || record.name.startsWith('_mta')),
	),
)

const inboundMailRoutingRecords = computed(() =>
	domainRecords.value.filter((record) => record.type === 'MX'),
)

const serviceConfigurationRecords = computed(() =>
	domainRecords.value.filter((record) => record.type === 'CNAME'),
)

const serviceDiscoveryRecords = computed(() =>
	domainRecords.value.filter((record) => record.type === 'SRV'),
)

const transportSecurityRecords = computed(() =>
	domainRecords.value.filter(
		(record) =>
			record.type === 'TXT' &&
			(record.name.startsWith('_smtp') || record.name.startsWith('_mta')),
	),
)

const deleteDomain = createResource({
	url: 'mail.api.admin.delete_domain',
	makeParams: () => ({ domain_id: domainId }),
	onSuccess: () => {
		router.push({ name: 'Domains' })
		showConfirmDialog.value = false
		raiseToast('Domain deleted.')
	},
	onError: (error: ResourceError) => raiseToast(getErrorMessage(error), 'error'),
})

const BREADCRUMBS = computed(() => [
	{ label: __('Domains'), route: '/dashboard/domains' },
	{ label: domain.data?.name || domainId },
])

const confirmDialogAction = ref<'deleteDomain'>('deleteDomain')

const badge = computed<{ label: string; theme: 'green' | 'gray' }>(() =>
	(domain.data as DomainData | undefined)?.is_enabled
		? { label: __('Enabled'), theme: 'green' }
		: { label: __('Disabled'), theme: 'gray' },
)

const confirmDialogOptions = computed(() => {
	const config = {
		deleteDomain: {
			title: __('Delete Domain'),
			message: __(
				'Are you sure you want to delete this domain? This action cannot be undone.',
			),
			action: deleteDomain.submit,
		},
	}[confirmDialogAction.value]

	return {
		title: config.title,
		message: config.message,
		size: 'xl',
		icon: { name: 'alert-triangle', appearance: 'warning' },
		actions: [{ label: __('Confirm'), variant: 'solid', onClick: config.action }],
	}
})

const dropdownOptions = computed(() => [
	{
		group: '',
		items: [
			{
				label: __('Delete Domain'),
				icon: 'trash-2',
				onClick: () => {
					confirmDialogAction.value = 'deleteDomain'
					showConfirmDialog.value = true
				},
			},
		],
	},
])

const BANNER = {
	title: __('Set Up Your Domain'),
	message: __("Add the following records to your domain's DNS settings."),
	subtitle: __('DNS changes may take up to 48 hours to propagate globally.'),
}
</script>

<style scoped>
.expand-enter-active,
.expand-leave-active {
	@apply max-h-full opacity-100 transition-all duration-700 ease-linear;
}

.expand-enter-from,
.expand-leave-to {
	@apply max-h-0 p-0 opacity-0;
}
</style>
