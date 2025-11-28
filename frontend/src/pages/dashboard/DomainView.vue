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
				:label="__(domain.doc.enabled ? 'Verify' : 'Enable')"
				@click="
					domain.doc.enabled
						? domain.verifyDnsRecords.submit()
						: domain.setValue.submit({ enabled: 1 })
				"
			/>
		</template>
		<template #default>
			<transition name="expand">
				<div
					v-if="domain.doc.enabled && !domain.doc.is_verified"
					class="bg-surface-blue-1 overflow-hidden rounded-md border"
				>
					<div class="space-y-2 p-4">
						<h3 class="font-medium">{{ BANNER.title }}</h3>
						<p>{{ BANNER.message }}</p>
						<p class="text-ink-gray-4 text-sm">{{ BANNER.subtitle }}</p>
					</div>
				</div>
			</transition>
			<div class="space-y-4 rounded-md border p-4">
				<h2>{{ __('DNS Records') }}</h2>
				<ListView
					class="flex-1"
					:columns="LIST_COLUMNS"
					:rows="domain.doc.dns_records"
					:options="{ selectable: false }"
					row-key="name"
				>
					<ListHeader />
					<ListRows>
						<ListRow v-for="row in domain.doc.dns_records" :key="row.name" :row="row">
							<template #default="{ item }">
								<ListRowItem>
									<div class="cursor-copy" @click="copyToClipBoard(item)">
										{{ item }}
									</div>
								</ListRowItem>
							</template>
						</ListRow>
					</ListRows>
				</ListView>
			</div>
		</template>
	</DashboardLayout>
	<Dialog v-model="showConfirmDialog" :options="confirmDialogOptions" />
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
	Button,
	Dialog,
	Dropdown,
	ListHeader,
	ListRow,
	ListRowItem,
	ListRows,
	ListView,
	createDocumentResource,
} from 'frappe-ui'

import { copyToClipBoard, raiseToast } from '@/utils'
import DashboardLayout from '@/components/DashboardLayout.vue'

const { domainName } = defineProps<{ domainName: string }>()

const router = useRouter()

const showConfirmDialog = ref(false)

const domain = createDocumentResource({
	doctype: 'Mail Domain',
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

const confirmDialogAction = ref<'refreshDnsRecords' | 'rotateDkimKeys' | 'disableDomain'>(
	'refreshDnsRecords',
)

const badge = computed(() =>
	domain.doc.is_verified
		? { label: __('Verified'), theme: 'green' }
		: domain.doc.enabled
			? { label: __('Not Verified'), theme: 'orange' }
			: { label: __('Disabled'), theme: 'gray' },
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
		disableDomain: {
			title: __('Disable Domain'),
			message: __(
				`Are you sure you want to disable this domain? Email services for this domain will stop working immediately.`,
			),
			action: () => domain.setValue.submit({ enabled: 0 }),
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
		label: __('Disable Domain'),
		icon: 'eye-off',
		onClick: () => {
			confirmDialogAction.value = 'disableDomain'
			showConfirmDialog.value = true
		},
		condition: () => domain.doc.enabled,
	},
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
		onClick: () => window.open(`/app/mail-domain/${domainName}`, '_blank')?.focus(),
	},
])

const LIST_COLUMNS = [
	{ label: 'Type', key: 'type', width: '10%' },
	{ label: 'Host', key: 'host', width: '20%' },
	{ label: 'Priority', key: 'priority', width: '10%' },
	{ label: 'Value', key: 'value', width: '50%' },
	{ label: 'TTL (Recommended)', key: 'ttl', width: '10%' },
]

const BANNER = {
	title: __('Verify your DNS Records'),
	message: __(
		"Add the following records to your domain's DNS settings. Then click on 'Verify' to complete your domain setup.",
	),
	subtitle: __('Note: DNS changes may take up to 48 hours to propagate globally.'),
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
