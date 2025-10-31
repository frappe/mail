<template>
	<div
		ref="multiselectInput"
		:class="[$attrs.class, 'flex w-full flex-wrap items-center gap-2']"
		@click="isFocused = true"
	>
		<div
			v-for="value in displayedValues"
			ref="valueRefs"
			:key="value"
			theme="gray"
			variant="subtle"
			class="!text-ink-gray-7 bg-surface-gray-2 flex min-h-7 cursor-default items-center rounded px-2 text-base"
			@keydown.delete.capture.stop="removeLastValue"
		>
			<span>{{ value }}</span>
			<X
				v-if="!isMobile || isFocused"
				class="ml-1.5 h-3.5 w-3.5 cursor-pointer"
				@click.stop="removeValue(value)"
			/>
		</div>
		<span v-if="isMobile && !isFocused && values.length > 2" class="text-ink-gray-6">
			{{ `+${values.length - 2}` }}
		</span>
		<div class="flex-1">
			<Combobox v-model="selectedValue" nullable>
				<Popover v-model:show="showOptions" class="w-full">
					<template #target="{ togglePopover }">
						<ComboboxInput
							ref="searchInput"
							class="search-input form-input w-full border-none !bg-inherit focus:border-none focus:!shadow-none focus-visible:!ring-0"
							type="text"
							:value="query"
							autocomplete="off"
							@change="handleQueryChange"
							@keydown.enter="handleEnterKey"
							@focus="handleFocus(togglePopover)"
							@blur="handleBlur"
							@keydown.delete.capture.stop="removeLastValue"
						/>
					</template>
					<template #body="{ isOpen }">
						<div v-show="isOpen">
							<div
								v-if="query && options.length"
								class="bg-surface-modal mt-1 rounded-lg py-1 text-sm shadow-2xl"
							>
								<ComboboxOptions
									class="my-1 max-h-[12rem] overflow-y-auto px-1.5"
									static
								>
									<ComboboxOption
										v-for="option in options"
										:key="option.value"
										v-slot="{ active }"
										:value="option"
									>
										<li
											:class="[
												'flex cursor-pointer items-center rounded px-2 py-1 text-base',
												{ 'bg-surface-gray-2': active },
											]"
										>
											<Avatar
												class="mr-2"
												:label="option.value"
												:image="option.image"
												size="lg"
											/>
											<div class="text-ink-gray-7 flex flex-col gap-1 p-1">
												<div class="text-sm font-medium">
													{{ option.label }}
												</div>
												<div class="text-ink-gray-5 text-sm">
													{{ option.value }}
												</div>
											</div>
										</li>
									</ComboboxOption>
								</ComboboxOptions>
							</div>
						</div>
					</template>
				</Popover>
			</Combobox>
		</div>
	</div>
	<ErrorMessage v-if="error" class="mt-2 pl-2" :message="error" />
</template>

<script setup lang="ts">
import { computed, nextTick, ref, useTemplateRef } from 'vue'
import { Combobox, ComboboxInput, ComboboxOption, ComboboxOptions } from '@headlessui/vue'
import { onClickOutside, useDebounceFn } from '@vueuse/core'
import { X } from 'lucide-vue-next'
import { Avatar, ErrorMessage, Popover, createResource } from 'frappe-ui'

import { useScreenSize } from '@/utils/composables'

interface Option {
	label: string
	value: string
	image?: string
}

interface Props {
	validate?: (value: string) => boolean
	errorMessage?: (value: string) => string
}

const props = withDefaults(defineProps<Props>(), {
	validate: undefined,
	errorMessage: (value: string) => `${value} is an Invalid value`,
})

const values = defineModel<string[]>({ default: () => [] })

const multiselectInput = useTemplateRef('multiselectInput')
const valueRefs = useTemplateRef('valueRefs')
const searchInput = useTemplateRef('searchInput')

const isFocused = ref(false)
const query = ref('')
const error = ref<string | null>(null)
const showOptions = ref(false)

onClickOutside(multiselectInput, () => {
	isFocused.value = false
})

const { isMobile } = useScreenSize()

const displayedValues = computed(() => {
	if (!values.value?.length) return []
	if (values.value.length <= 2 || !isMobile.value || isFocused.value) return values.value

	return values.value.slice(0, 2)
})

const mailContacts = createResource({
	url: 'mail.api.mail.get_mail_contacts',
	makeParams: (params: { txt: string }) => ({ txt: params.txt }),
	transform: (data: Array<{ full_name?: string; email: string; user_image?: string }>) =>
		data
			.filter((option) => option.email)
			.map((option) => ({
				label: option.full_name || option.email,
				value: option.email,
				image: option.user_image,
			}))
			.filter((d) => !values.value?.includes(d.value)),
	auto: false,
})

const debouncedSearch = useDebounceFn(
	(searchText: string) => mailContacts.reload({ txt: searchText }),
	300,
)

const options = computed<Option[]>(() => {
	const searchedContacts = mailContacts.data || []

	if (query.value && !searchedContacts.some((c) => c.value === query.value))
		return [...searchedContacts, { label: query.value, value: query.value }]

	return searchedContacts
})

const selectedValue = computed({
	get: () => query.value || '',
	set: (val: string | Option | null) => {
		query.value = ''
		if (val) showOptions.value = false

		if (val && typeof val === 'object' && 'value' in val) addValue(val.value)
	},
})

const handleQueryChange = (e: Event) => {
	const target = e.target as HTMLInputElement
	const newValue = target.value || ''

	query.value = newValue
	showOptions.value = true

	if (newValue) debouncedSearch(newValue)
}

const handleEnterKey = () => addValue(query.value)

const handleFocus = (togglePopover: () => void) => {
	togglePopover()
	isFocused.value = true
}

const handleBlur = () => (isFocused.value = false)

const addValue = (input: string) => {
	error.value = null
	if (!input) return

	const newValues = input
		.split(',')
		.map((v) => v.trim())
		.filter(Boolean)

	for (const val of newValues) {
		if (values.value?.includes(val)) continue

		if (props.validate && !props.validate(val)) {
			error.value = props.errorMessage(val)
			return
		}

		values.value = values.value ? [...values.value, val] : [val]
	}
}

const removeValue = (value: string) => (values.value = values.value.filter((v) => v !== value))

const removeLastValue = () => {
	if (query.value) return

	const lastValueRef = valueRefs.value?.[valueRefs.value.length - 1]?.$el

	if (document.activeElement !== lastValueRef) return lastValueRef?.focus()

	values.value.pop()

	nextTick(() => {
		if (values.value.length) {
			const newLastRef = valueRefs.value[valueRefs.value.length - 1].$el
			newLastRef?.focus()
		} else setFocus()
	})
}

const setFocus = () => searchInput.value?.$el?.focus()

defineExpose({ setFocus })
</script>
