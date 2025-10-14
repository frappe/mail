import { reactive } from 'vue'
import { defineStore } from 'pinia'

export const searchStore = defineStore('search-filter', () => {
	const searchFilter = reactive({ ...DEFAULT_FILTER })

	const resetSearchFilter = () => Object.assign(searchFilter, DEFAULT_FILTER)

	return { searchFilter, resetSearchFilter }
})

const DEFAULT_FILTER = {
	text: '',
	inMailbox: '',
	subject: '',
	from: '',
	to: '',
	cc: '',
	bcc: '',
	after: '',
	before: '',
}
