<template>
	<DashboardLayout v-if="contact?.doc" :breadcrumbs="breadcrumbs">
		<template #actions>
			<Button
				variant="solid"
				:label="__('Save')"
				:loading="contact.save.loading"
				:disabled="
					contact.get.loading ||
					JSON.stringify(contact.doc) === JSON.stringify(contact.originalDoc)
				"
				@click="contact.save.submit"
			/>
		</template>
		<template #default>
			<div class="grid grid-cols-2 gap-5">
				<DashboardCard
					:title="__('General Information')"
					:button-label="__('Edit')"
					class="h-[14.5rem]"
					@action="showEditGeneral = true"
				>
					<InformationField :label="__('Name')" :value="contact.doc.full_name" />
					<InformationField :label="__('Kind')" :value="contact.doc.kind" />
					<InformationField
						:label="__('Created On')"
						:value="dayjs(contact.doc.created_at).format('MMM D YYYY, h:mm A')"
					/>
					<InformationField
						:label="__('Updated On')"
						:value="dayjs(contact.doc.updated_at).format('MMM D YYYY, h:mm A')"
					/>
				</DashboardCard>

				<ListCard
					:rows="contact.doc.address_books"
					:title="__('Address Books')"
					:column-label="__('Name')"
					row="address_book_name"
					class="h-[14.5rem]"
					@add="showAddAddressBook = true"
					@remove="
						(selections) =>
							(contact.doc.address_books = contact.doc.address_books.filter(
								(e) => !selections.has(e.idx),
							))
					"
				/>

				<DashboardCard
					:title="__('Emails')"
					:button-label="__('Add')"
					class="col-span-2 h-[14.5rem]"
					@action="showAddEmail = true"
				>
					<ListView
						:columns="EMAIL_COLUMNS"
						:rows="contact.doc.emails"
						row-key="address"
						:options="{ emptyState: { title: '', description: __('No emails.') } }"
						class="flex-1 overflow-auto p-4"
					>
						<ListHeader />
						<ListRows v-if="contact.doc.emails.length" />
						<ListEmptyState v-else />
						<ListSelectBanner>
							<template #actions="{ selections, unselectAll }">
								<Button
									variant="ghost"
									:label="__('Remove')"
									theme="red"
									@click="
										() => {
											contact.doc.emails = contact.doc.emails.filter(
												(e) => !selections.has(e.address),
											)
											unselectAll()
										}
									"
								/>
							</template>
						</ListSelectBanner>
					</ListView>
				</DashboardCard>

				<DashboardCard
					:title="__('Phones')"
					:button-label="__('Add')"
					class="col-span-2 h-[14.5rem]"
					@action="showAddPhone = true"
				>
					<ListView
						:columns="PHONE_COLUMNS"
						:rows="contact.doc.phones"
						row-key="number"
						:options="{ emptyState: { title: '', description: __('No phones.') } }"
						class="flex-1 overflow-auto p-4"
					>
						<ListHeader />
						<ListRows v-if="contact.doc.phones.length" />
						<ListEmptyState v-else />
						<ListSelectBanner>
							<template #actions="{ selections, unselectAll }">
								<Button
									variant="ghost"
									:label="__('Remove')"
									theme="red"
									@click="
										() => {
											contact.doc.phones = contact.doc.phones.filter(
												(e) => !selections.has(e.number),
											)
											unselectAll()
										}
									"
								/>
							</template>
						</ListSelectBanner>
					</ListView>
				</DashboardCard>

				<DashboardCard
					:title="__('Addresses')"
					:button-label="__('Add')"
					class="col-span-2 h-[14.5rem]"
					@action="showAddAddress = true"
				>
					<ListView
						:columns="ADDRESS_COLUMNS"
						:rows="contact.doc.addresses"
						row-key="idx"
						:options="{ emptyState: { title: '', description: __('No addresses.') } }"
						class="flex-1 overflow-auto p-4"
					>
						<ListHeader />
						<ListRows v-if="contact.doc.addresses.length" />
						<ListEmptyState v-else />
						<ListSelectBanner>
							<template #actions="{ selections, unselectAll }">
								<Button
									variant="ghost"
									:label="__('Remove')"
									theme="red"
									@click="
										() => {
											contact.doc.addresses = contact.doc.addresses.filter(
												(e) => !selections.has(e.idx),
											)
											unselectAll()
										}
									"
								/>
							</template>
						</ListSelectBanner>
					</ListView>
				</DashboardCard>
			</div>
		</template>
	</DashboardLayout>

	<EditContactModal
		v-if="contact?.originalDoc"
		v-model="showEditGeneral"
		:full-name="contact.doc.full_name"
		:kind="contact.doc.kind"
		@save="
			(val) => {
				contact.doc.full_name = val.fullName
				contact.doc.kind = val.kind
				contact.save.submit()
			}
		"
	/>
	<AddContactAddressBookModal
		v-if="contact?.originalDoc"
		v-model="showAddAddressBook"
		@add="(val) => contact.doc.address_books.push(val)"
	/>
	<AddContactEmailModal
		v-if="contact?.originalDoc"
		v-model="showAddEmail"
		@add="(val) => contact.doc.emails.push(val)"
	/>
	<AddContactPhoneModal
		v-if="contact?.originalDoc"
		v-model="showAddPhone"
		@add="(val) => contact.doc.phones.push(val)"
	/>
	<AddContactAddressModal
		v-if="contact?.originalDoc"
		v-model="showAddAddress"
		@add="(val) => contact.doc.addresses.push(val)"
	/>
</template>

<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
	Button,
	ListEmptyState,
	ListHeader,
	ListRows,
	ListSelectBanner,
	ListView,
	createDocumentResource,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import DashboardCard from '@/components/DashboardCard.vue'
import DashboardLayout from '@/components/DashboardLayout.vue'
import InformationField from '@/components/InformationField.vue'
import ListCard from '@/components/ListCard.vue'
import AddContactAddressBookModal from '@/components/Modals/AddContactAddressBookModal.vue'
import AddContactAddressModal from '@/components/Modals/AddContactAddressModal.vue'
import AddContactEmailModal from '@/components/Modals/AddContactEmailModal.vue'
import AddContactPhoneModal from '@/components/Modals/AddContactPhoneModal.vue'
import EditContactModal from '@/components/Modals/EditContactModal.vue'

const { contactName } = defineProps<{ contactName: string }>()

const user = inject('$user')
const dayjs = inject('$dayjs')

const router = useRouter()

const showEditGeneral = ref(false)
const showAddAddressBook = ref(false)
const showAddEmail = ref(false)
const showAddPhone = ref(false)
const showAddAddress = ref(false)

const contact = createDocumentResource({
	doctype: 'Contact Card',
	name: `${user.data.name}|${contactName}`,
	onError: () => router.replace({ name: 'Contacts' }),
	setValue: {
		onSuccess: () => raiseToast(__('Contact updated.')),
		onError: (error) => {
			contact.reload()
			raiseToast(error.messages[0], 'error')
		},
	},
})

const breadcrumbs = computed(() => [
	{ label: __('Contacts'), route: '/contacts' },
	{ label: contact.doc?.full_name || contactName },
])

const EMAIL_COLUMNS = [
	{ label: __('Address'), key: 'address' },
	{ label: __('Type'), key: 'type' },
	{ label: __('Label'), key: 'label' },
]

const PHONE_COLUMNS = [
	{ label: __('Number'), key: 'number' },
	{ label: __('Type'), key: 'type' },
	{ label: __('Label'), key: 'label' },
]

const ADDRESS_COLUMNS = [
	{ label: __('Type'), key: 'type', width: '15%' },
	{ label: __('Street'), key: 'street', width: '20%' },
	{ label: __('Locality'), key: 'locality', width: '20%' },
	{ label: __('Region'), key: 'region', width: '15%' },
	{ label: __('Postcode'), key: 'postcode', width: '15%' },
	{ label: __('Country'), key: 'country', width: '15%' },
]
</script>
