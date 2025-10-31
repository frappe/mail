<template>
	<Combobox v-model="selectedValue" nullable as="div">
		<ComboboxLabel v-if="attrs.label" :class="labelClasses">{{ attrs.label }}</ComboboxLabel>
		<Popover v-model:show="showOptions" class="w-full">
			<template #target="{ open: openPopover, togglePopover }">
				<slot name="target" v-bind="{ open: openPopover, togglePopover }">
					<div class="w-full">
						<button
							class="flex w-full items-center justify-between focus:outline-none"
							:class="inputClasses"
							@click="() => togglePopover()"
						>
							<div class="flex items-center">
								<slot name="prefix" />
								<span
									v-if="selectedValue"
									class="overflow-hidden text-ellipsis whitespace-nowrap text-base leading-5"
								>
									{{ displayValue(selectedValue) }}
								</span>
								<span v-else class="text-ink-gray-4 text-base leading-5">
									{{ placeholder || '' }}
								</span>
							</div>
							<ChevronDown class="ml-1.5 h-3.5 w-3.5" />
						</button>
					</div>
				</slot>
			</template>
			<template #body="{ isOpen }">
				<div v-show="isOpen && !disabled">
					<div class="bg-surface-white mt-1 rounded-lg py-1 text-base shadow-2xl">
						<div class="relative mb-2 px-1.5 pt-0.5" :class="{ hidden: !showSearch }">
							<ComboboxInput
								ref="search"
								class="form-input w-full"
								type="text"
								:value="query"
								autocomplete="off"
								placeholder="Search"
								@change="query = $event.target.value"
							/>
							<button
								class="absolute right-1.5 inline-flex h-7 w-7 items-center justify-center"
								@click="selectedValue = null"
							>
								<X class="stroke-1.5 h-4 w-4" />
							</button>
						</div>
						<ComboboxOptions class="my-1 max-h-[12rem] overflow-y-auto px-1.5" static>
							<div
								v-for="group in groups"
								v-show="group.items.length > 0"
								:key="group.key"
							>
								<div
									v-if="group.group && !group.hideLabel"
									class="text-ink-gray-4 px-2.5 py-1.5 text-sm font-medium"
								>
									{{ group.group }}
								</div>
								<ComboboxOption
									v-for="option in group.items"
									:key="option.value"
									v-slot="{ active, selected }"
									as="template"
									:value="option"
								>
									<li
										:class="[
											'flex cursor-pointer items-center rounded px-2.5 py-2 text-base',
											{ 'bg-surface-gray-2': active },
										]"
									>
										<slot
											name="item-prefix"
											v-bind="{ active, selected, option }"
										/>
										<slot
											name="item-label"
											v-bind="{ active, selected, option }"
										>
											<div class="flex flex-col space-y-1">
												<div>
													{{ option.label || option }}
												</div>
												<div
													v-if="option.label != option.description"
													class="text-ink-gray-6 text-xs"
													v-html="option.description"
												/>
											</div>
										</slot>
									</li>
								</ComboboxOption>
							</div>
							<li
								v-if="groups.length == 0"
								class="text-ink-gray-5 mt-1.5 rounded-md px-2.5 py-1.5 text-base"
							>
								No results found
							</li>
						</ComboboxOptions>
						<div v-if="slots.footer" class="border-t p-1.5 pb-0.5">
							<slot name="footer" v-bind="{ value: search?.el._value, close }" />
						</div>
					</div>
				</div>
			</template>
		</Popover>
	</Combobox>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, useAttrs, useSlots, watch } from 'vue'
import {
	Combobox,
	ComboboxInput,
	ComboboxLabel,
	ComboboxOption,
	ComboboxOptions,
} from '@headlessui/vue'
import { ChevronDown, X } from 'lucide-vue-next'
import { Popover } from 'frappe-ui'

const props = withDefaults(
	defineProps<{
		modelValue: string
		options?: (object | string)[]
		size?: 'sm' | 'md'
		variant?: 'subtle' | 'outline' | 'disabled'
		placeholder?: string
		disabled?: boolean
		filterable?: boolean
		showSearch?: boolean
	}>(),
	{
		options: () => [],
		size: 'sm',
		variant: 'subtle',
		placeholder: '',
		disabled: false,
		filterable: true,
		showSearch: true,
	},
)

const emit = defineEmits(['update:modelValue', 'update:query', 'change'])

const query = ref('')
const showOptions = ref(false)
const search = ref(null)

const attrs = useAttrs()
const slots = useSlots()

const valuePropPassed = computed(() => 'value' in attrs)

const selectedValue = computed({
	get() {
		return valuePropPassed.value ? attrs.value : props.modelValue
	},
	set(val) {
		query.value = ''
		if (val) {
			showOptions.value = false
		}
		emit(valuePropPassed.value ? 'change' : 'update:modelValue', val)
	},
})

function close() {
	showOptions.value = false
}

const groups = computed(() => {
	if (!props.options || props.options.length == 0) return []

	const groups = props.options[0]?.group ? props.options : [{ group: '', items: props.options }]

	return groups
		.map((group, i) => {
			return {
				key: i,
				group: group.group,
				hideLabel: group.hideLabel || false,
				items: props.filterable ? filterOptions(group.items) : group.items,
			}
		})
		.filter((group) => group.items.length > 0)
})

function filterOptions(options) {
	if (!query.value) {
		return options
	}
	return options.filter((option) => {
		const searchTexts = [option.label, option.value]
		return searchTexts.some((text) =>
			(text || '').toString().toLowerCase().includes(query.value.toLowerCase()),
		)
	})
}

function displayValue(option) {
	if (typeof option === 'string') {
		const allOptions = groups.value.flatMap((group) => group.items)
		const selectedOption = allOptions.find((o) => o.value === option)
		return selectedOption?.label || option
	}
	return option?.label
}

watch(query, (q) => {
	emit('update:query', q)
})

watch(showOptions, (val) => {
	if (val) {
		nextTick(() => {
			search.value.el.focus()
		})
	}
})

const textColor = computed(() => {
	return props.disabled ? 'text-ink-gray-5' : 'text-ink-gray-7'
})

const inputClasses = computed(() => {
	const sizeClasses = {
		sm: 'text-base rounded h-7',
		md: 'text-base rounded h-8',
		lg: 'text-lg rounded-md h-10',
		xl: 'text-xl rounded-md h-10',
	}[props.size]

	const paddingClasses = {
		sm: 'py-1.5 px-2',
		md: 'py-1.5 px-2.5',
		lg: 'py-1.5 px-3',
		xl: 'py-1.5 px-3',
	}[props.size]

	const variant = props.disabled ? 'disabled' : props.variant
	const variantClasses = {
		subtle: 'bg-surface-gray-2 placeholder-ink-gray-4 hover:bg-surface-gray-3 focus:shadow-sm focus:ring-0 focus-visible:ring-2',
		outline:
			'border border-outline-gray-2 bg-surface-white placeholder-ink-gray-4 hover:border-outline-gray-3 hover:shadow-sm focus:bg-surface-white focus:border-outline-gray-4 focus:shadow-sm focus:ring-0 focus-visible:ring-2 focus-visible:ring-outline-gray-3',
		disabled: [
			'border bg-surface-gray-1 placeholder-ink-gray-3 cursor-default',
			props.variant === 'outline' ? 'border-outline-gray-2' : 'border-transparent',
		],
	}[variant]

	return [
		sizeClasses,
		paddingClasses,
		variantClasses,
		textColor.value,
		'transition-colors w-full',
	]
})

const labelClasses = computed(() => [
	{
		sm: 'text-xs',
		md: 'text-base',
	}[props.size],
	'text-ink-gray-5 block mb-1.5',
])

defineExpose({ query })
</script>
