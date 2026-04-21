<template>
	<DashboardLayout v-if="contact?.doc" :breadcrumbs="breadcrumbs">
		<template #actions>
			<Dropdown :options="DROPDOWN_OPTIONS">
				<Button icon="more-horizontal" class="text-ink-gray-5" />
			</Dropdown>
		</template>
		<template #default>
			<div class="grid grid-cols-2 gap-5">
				<DashboardCard
					:title="__('General Information')"
					:button-label="__('Edit')"
					class="h-[14.5rem] max-sm:col-span-2"
					@action="showEditGeneral = true"
				>
					<InformationField :label="__('Name')" :value="contact.doc.full_name" />
					<InformationField :label="__('Kind')" :value="capitalize(contact.doc.kind)" />
					<InformationField
						:label="__('Created On')"
						:value="dayjs(contact.doc.created_at).format('MMM D YYYY, h:mm A')"
					/>
					<InformationField
						:label="__('Updated On')"
						:value="dayjs(contact.doc.updated_at).format('MMM D YYYY, h:mm A')"
					/>
				</DashboardCard>

				<DashboardCard
					:title="__('Address Books')"
					class="h-[14.5rem] max-sm:col-span-2"
					@action="showAddAddressBook = true"
				>
					<ListView
						ref="addressBooksList"
						:columns="ADDRESS_BOOK_COLUMNS"
						:rows="contact.doc.address_books"
						row-key="address_book_id"
						:options="{
							emptyState: { title: '', description: __('No address books.') },
						}"
						class="flex-1 overflow-auto p-4"
					>
						<ListHeader />
						<ListRows v-if="contact.doc.address_books.length" />
						<ListEmptyState v-else />
						<ListSelectBanner>
							<template #actions>
								<Button
									variant="ghost"
									:label="__('Remove')"
									theme="red"
									@click="showRemoveAddressBooks = true"
								/>
							</template>
						</ListSelectBanner>
					</ListView>
				</DashboardCard>

				<DashboardCard
					:title="__('Emails')"
					class="col-span-2 h-[14.5rem]"
					@action="showAddEmail = true"
				>
					<ListView
						ref="emailsList"
						:columns="EMAIL_COLUMNS"
						:rows="contact.doc.emails.map((c) => ({ ...c, type: capitalize(c.type) }))"
						row-key="address"
						:options="{ emptyState: { title: '', description: __('No emails.') } }"
						class="flex-1 overflow-auto p-4"
					>
						<ListHeader />
						<ListRows v-if="contact.doc.emails.length" />
						<ListEmptyState v-else />
						<ListSelectBanner>
							<template #actions>
								<Button
									variant="ghost"
									:label="__('Remove')"
									theme="red"
									@click="showRemoveEmails = true"
								/>
							</template>
						</ListSelectBanner>
					</ListView>
				</DashboardCard>

				<DashboardCard
					:title="__('Phones')"
					class="col-span-2 h-[14.5rem]"
					@action="showAddPhone = true"
				>
					<ListView
						ref="phonesList"
						:columns="PHONE_COLUMNS"
						:rows="contact.doc.phones.map((p) => ({ ...p, type: capitalize(p.type) }))"
						row-key="number"
						:options="{ emptyState: { title: '', description: __('No phones.') } }"
						class="flex-1 overflow-auto p-4"
					>
						<ListHeader />
						<ListRows v-if="contact.doc.phones.length" />
						<ListEmptyState v-else />
						<ListSelectBanner>
							<template #actions>
								<Button
									variant="ghost"
									:label="__('Remove')"
									theme="red"
									@click="showRemovePhones = true"
								/>
							</template>
						</ListSelectBanner>
					</ListView>
				</DashboardCard>

				<DashboardCard
					:title="__('Addresses')"
					class="col-span-2 h-[14.5rem]"
					@action="showAddAddress = true"
				>
					<ListView
						ref="addressesList"
						:columns="ADDRESS_COLUMNS"
						:rows="
							contact.doc.addresses.map((a) => ({ ...a, type: capitalize(a.type) }))
						"
						row-key="idx"
						:options="{ emptyState: { title: '', description: __('No addresses.') } }"
						class="flex-1 overflow-auto p-4"
					>
						<ListHeader />
						<ListRows v-if="contact.doc.addresses.length" />
						<ListEmptyState v-else />
						<ListSelectBanner>
							<template #actions>
								<Button
									variant="ghost"
									:label="__('Remove')"
									theme="red"
									@click="showRemoveAddresses = true"
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
		@add="
			(val) => {
				contact.doc.address_books.push(val)
				contact.save.submit()
			}
		"
	/>
	<AddContactEmailModal
		v-if="contact?.originalDoc"
		v-model="showAddEmail"
		@add="
			(val) => {
				contact.doc.emails.push(val)
				contact.save.submit()
			}
		"
	/>
	<AddContactPhoneModal
		v-if="contact?.originalDoc"
		v-model="showAddPhone"
		@add="
			(val) => {
				contact.doc.phones.push(val)
				contact.save.submit()
			}
		"
	/>
	<AddContactAddressModal
		v-if="contact?.originalDoc"
		v-model="showAddAddress"
		@add="
			(val) => {
				contact.doc.addresses.push(val)
				contact.save.submit()
			}
		"
	/>
	<Dialog v-model="showDeleteContact" :options="deleteContactOptions" />
	<Dialog v-model="showRemoveAddressBooks" :options="removeAddressBooksOptions" />
	<Dialog v-model="showRemoveEmails" :options="removeEmailsOptions" />
	<Dialog v-model="showRemovePhones" :options="removePhonesOptions" />
	<Dialog v-model="showRemoveAddresses" :options="removeAddressesOptions" />
</template>

<script setup lang="ts">
import { capitalize, computed, inject, ref, useTemplateRef } from 'vue'
import { useRouter } from 'vue-router'
import { Trash2 } from 'lucide-vue-next'
import {
	Button,
	Dialog,
	Dropdown,
	ListEmptyState,
	ListHeader,
	ListRows,
	ListSelectBanner,
	ListView,
	createDocumentResource,
	createResource,
} from 'frappe-ui'

import { raiseToast } from '@/utils'
import { userStore } from '@/stores/user'
import DashboardCard from '@/components/DashboardCard.vue'
import DashboardLayout from '@/components/DashboardLayout.vue'
import InformationField from '@/components/InformationField.vue'
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
const showRemoveAddressBooks = ref(false)
const showRemoveEmails = ref(false)
const showRemovePhones = ref(false)
const showRemoveAddresses = ref(false)
const showDeleteContact = ref(false)

const { account } = userStore()

const contact = createDocumentResource({
	doctype: 'Contact Card',
	name: `${account}|${contactName}`,
	onError: () => router.replace({ name: 'Contacts' }),
	setValue: {
		onSuccess: () => raiseToast(__('Contact updated.')),
		onError: (error) => {
			contact.reload()
			raiseToast(error.messages[0], 'error')
		},
	},
})

const deleteContact = createResource({
	url: 'mail.client.doctype.contact_card.contact_card.delete_contact_cards',
	makeParams: () => ({ user: user.data.name, ids: [contact.doc.id] }),
	onSuccess: () => {
		showDeleteContact.value = false
		raiseToast(__('Contact deleted.'))
		router.push({ name: 'Contacts' })
	},
	onError: (error) => {
		showDeleteContact.value = false
		raiseToast(error.messages[0], 'error')
	},
})

const deleteContactOptions = computed(() => ({
	title: __('Delete Contact'),
	message: __('Are you sure you want to delete the contact for {0}?', [contact.doc?.full_name]),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [{ label: __('Confirm'), variant: 'solid', onClick: deleteContact.submit }],
}))

const addressBooksList = useTemplateRef('addressBooksList')
const removeAddressBooksOptions = computed(() => ({
	title: __('Remove from Address Books'),
	message: __('Are you sure you want to remove this contact from the selected address books?'),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [
		{
			label: __('Confirm'),
			variant: 'solid',
			onClick: () => {
				contact.doc.address_books = contact.doc.address_books.filter(
					(ab) => !addressBooksList.value?.selections.has(ab.address_book_id),
				)
				contact.save.submit()
				addressBooksList.value?.toggleAllRows()
				showRemoveAddressBooks.value = false
			},
		},
	],
}))

const emailsList = useTemplateRef('emailsList')
const removeEmailsOptions = computed(() => ({
	title: __('Remove Emails'),
	message: __('Are you sure you want to remove the selected emails?'),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [
		{
			label: __('Confirm'),
			variant: 'solid',
			onClick: () => {
				contact.doc.emails = contact.doc.emails.filter(
					(e) => !emailsList.value?.selections.has(e.address),
				)
				contact.save.submit()
				emailsList.value?.toggleAllRows()
				showRemoveEmails.value = false
			},
		},
	],
}))

const phonesList = useTemplateRef('phonesList')
const removePhonesOptions = computed(() => ({
	title: __('Remove Phones'),
	message: __('Are you sure you want to remove the selected phones?'),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [
		{
			label: __('Confirm'),
			variant: 'solid',
			onClick: () => {
				contact.doc.phones = contact.doc.phones.filter(
					(p) => !phonesList.value?.selections.has(p.number),
				)
				contact.save.submit()
				phonesList.value?.toggleAllRows()
				showRemovePhones.value = false
			},
		},
	],
}))

const addressesList = useTemplateRef('addressesList')
const removeAddressesOptions = computed(() => ({
	title: __('Remove Addresses'),
	message: __('Are you sure you want to remove the selected addresses?'),
	icon: { name: 'alert-triangle', appearance: 'warning' },
	actions: [
		{
			label: __('Confirm'),
			variant: 'solid',
			onClick: () => {
				contact.doc.addresses = contact.doc.addresses.filter(
					(address) => !addressesList.value?.selections.has(address.idx),
				)
				contact.save.submit()
				addressesList.value?.toggleAllRows()
				showRemoveAddresses.value = false
			},
		},
	],
}))

const breadcrumbs = computed(() => [
	{ label: __('Contacts'), route: '/contacts' },
	{ label: contact.doc?.full_name || contact.doc?.emails[0]?.address || contactName },
])

const ADDRESS_BOOK_COLUMNS = [{ label: __('Name'), key: 'address_book_name' }]

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

const DROPDOWN_OPTIONS = [
	{
		label: __('Delete'),
		onClick: () => (showDeleteContact.value = true),
		icon: Trash2,
	},
]
</script>
