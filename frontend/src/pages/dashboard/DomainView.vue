<template>
	<DashboardLayout
		v-if="domain?.doc"
		:breadcrumbs="BREADCRUMBS"
		:badge-label="badge.label"
		:badge-theme="badge.theme"
	>
		<template #actions>
			<Dropdown :options="dropdownOptions" :button="{ icon: 'more-horizontal' }" />
			<Button
				v-if="!domain.doc.is_verified"
				variant="solid"
				:label="__('Verify')"
				@click="domain.verifyDnsRecords.submit()"
			/>
		</template>
		<template #default>
			<transition name="expand">
				<div v-if="!domain.doc.is_verified" class="bg-surface-blue-1 rounded-md border">
					<div class="space-y-2 p-4">
						<h3 class="font-medium">{{ BANNER.title }}</h3>
						<p class="text-ink-gray-5 text-sm">{{ BANNER.message }}</p>
					</div>
				</div>
			</transition>
			<div class="rounded-md border">
				<h2 class="p-4">{{ __('DNS Records') }}</h2>
				<DNSRecords
					:title="__('Email Deliverability')"
					:description="
						__(
							'Email authentication records that verify your domain and protect outgoing mail from spoofing.',
						)
					"
					:records="
						domain.doc.dns_records.filter(
							(d) =>
								d.type === 'TXT' &&
								!(d.host.startsWith('_smtp') || d.host.startsWith('_mta')),
						)
					"
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
					:records="domain.doc.dns_records.filter((d) => d.type === 'MX')"
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
					:records="domain.doc.dns_records.filter((d) => d.type === 'CNAME')"
				/>
				<DNSRecords
					:title="__('Service Discovery Records')"
					:description="
						__(
							'Records that allow mail and sync apps to automatically locate and connect to your domain’s email, calendar, and contacts services.',
						)
					"
					:records="domain.doc.dns_records.filter((d) => d.type === 'SRV')"
				/>
				<DNSRecords
					:title="__('Email Transport Security Records')"
					:description="
						__(
							'TXT records that enforce encrypted mail delivery and provide reporting on failed or insecure SMTP connections.',
						)
					"
					:records="
						domain.doc.dns_records.filter(
							(d) =>
								d.type === 'TXT' &&
								(d.host.startsWith('_smtp') || d.host.startsWith('_mta')),
						)
					"
				/>
			</div>
		</template>
	</DashboardLayout>
	<Dialog v-model="showConfirmDialog" :options="confirmDialogOptions" />
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Dialog, Dropdown, createDocumentResource } from 'frappe-ui'

import { raiseToast } from '@/utils'
import DNSRecords from '@/components/DNSRecords.vue'
import DashboardLayout from '@/components/DashboardLayout.vue'

const { domainName } = defineProps<{ domainName: string }>()

const router = useRouter()

const showConfirmDialog = ref(false)

const domain = createDocumentResource({
	doctype: 'Principal',
	name: domainName,
	setValue: {
		onSuccess: () => {
			if (showConfirmDialog.value) showConfirmDialog.value = false
			raiseToast(__('Domain settings updated.'))
		},
		onError: (error) => {
			raiseToast(error.messages[0], 'error')
			domain.reload()
		},
	},
	delete: {
		onSuccess: () => {
			router.push({ name: 'Domains' })
			showConfirmDialog.value = false
			raiseToast('Domain deleted.')
		},
		onError: (error) => raiseToast(error.messages[0], 'error'),
	},
	whitelistedMethods: {
		verifyDnsRecords: {
			method: 'verify_dns_records',
			makeParams: () => ({ do_not_save: false }),
			onSuccess: (data: boolean) => {
				raiseToast(
					data ? __('DNS records verified.') : __('DNS verification failed.'),
					data ? 'success' : 'error',
				)
				domain.reload()
			},
			onError: (error) => {
				raiseToast(error.messages[0], 'error')
				domain.reload()
			},
		},
		refreshDnsRecords: {
			method: 'refresh_dns_records',
			makeParams: () => ({ do_not_save: false }),
			onSuccess: () => {
				showConfirmDialog.value = false
				raiseToast('DNS Records refreshed.')
				domain.reload()
			},
			onError: (error) => {
				raiseToast(error.messages[0], 'error')
				domain.reload()
			},
		},
		rotateDkimKeys: {
			method: 'rotate_dkim_keys',
			onSuccess: () => {
				showConfirmDialog.value = false
				raiseToast('DKIM Keys rotated.')
				domain.reload()
			},
			onError: (error) => {
				raiseToast(error.messages[0], 'error')
				domain.reload()
			},
		},
	},
	onError: () => router.replace({ name: 'Domains' }),
})

const BREADCRUMBS = [{ label: __('Domains'), route: '/dashboard/domains' }, { label: domainName }]

const confirmDialogAction = ref<'refreshDnsRecords' | 'rotateDkimKeys' | 'deleteDomain'>(
	'refreshDnsRecords',
)

const badge = computed(() =>
	domain.doc.is_verified
		? { label: __('Verified'), theme: 'green' }
		: { label: __('Not Verified'), theme: 'gray' },
)

const confirmDialogOptions = computed(() => {
	const config = {
		refreshDnsRecords: {
			title: __('Refresh DNS Records'),
			message: __(
				`Are you sure you want to refresh the DNS records? If there are any changes, you'll need to update the DNS settings with your DNS provider accordingly.`,
			),
			action: domain.refreshDnsRecords.submit,
		},
		rotateDkimKeys: {
			title: __('Rotate DKIM Keys'),
			message: __(
				`Are you sure you want to rotate the DKIM keys? This will generate new keys for email signing and may take up to 10 minutes to propagate across DNS servers. Emails sent during this period may fail DKIM verification.`,
			),
			action: domain.rotateDkimKeys.submit,
		},
		deleteDomain: {
			title: __('Delete Domain'),
			message: __(
				'Are you sure you want to delete this domain? This action cannot be undone.',
			),
			action: () => domain.delete.submit(),
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
				label: __('Refresh DNS Records'),
				icon: 'refresh-cw',
				onClick: () => {
					confirmDialogAction.value = 'refreshDnsRecords'
					showConfirmDialog.value = true
				},
			},
			{
				label: __('Rotate DKIM Keys'),
				icon: 'rotate-cw',
				onClick: () => {
					confirmDialogAction.value = 'rotateDkimKeys'
					showConfirmDialog.value = true
				},
			},
			{
				label: __('View in Desk'),
				icon: 'external-link',
				onClick: () => window.open(`/desk/mail-domain/${domainName}`, '_blank')?.focus(),
			},
		],
	},
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
	title: __('Verify your DNS Records'),
	message: __(
		"Add the following records to your domain's DNS settings. Then click on 'Verify' to complete your domain setup.",
	),
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
