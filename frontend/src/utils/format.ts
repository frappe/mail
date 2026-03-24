import dayjs from '@/utils/dayjs'

const DAYS_MAP: Record<string, string> = {
	su: 'Sunday',
	mo: 'Monday',
	tu: 'Tuesday',
	we: 'Wednesday',
	th: 'Thursday',
	fr: 'Friday',
	sa: 'Saturday',
}

const getByDayMessage = (byDay?: { day: string; nthOfPeriod?: number }[]) => {
	if (!byDay?.length) return ''
	const [first] = byDay

	if (first.nthOfPeriod === -1) return __(' on the last {0}', [DAYS_MAP[first.day]])

	if (first.nthOfPeriod != null)
		return __(' on the {0} {1}', [getNthLabel(first.nthOfPeriod), DAYS_MAP[first.day]])

	return __(' on {0}', [byDay.map((d) => DAYS_MAP[d.day]).join(', ')])
}

const getByMonthDayMessage = (byMonthDay?: number[]) => {
	if (!byMonthDay?.length) return ''
	const [day] = byMonthDay
	if (day === -1) return __(' on the last day')
	return __(' on the {0}', [getNthLabel(day)])
}

const getNthLabel = (n: number): string => {
	const suffixes: Record<number, string> = { 1: 'st', 2: 'nd', 3: 'rd' }
	const suffix = suffixes[n] ?? 'th'
	return `${n}${suffix}`
}

export const toTitleCase = (str: string) =>
	str
		?.toLowerCase()
		.split(' ')
		.map(function (word: string) {
			return word.charAt(0).toUpperCase().concat(word.substr(1))
		})
		.join(' ') || ''

export const getFormattedDate = (date: Date | string, omitDate = false) => {
	const dateObj = dayjs(date)
	const isCurrentYear = dateObj.year() === dayjs().year()
	if (omitDate) return dateObj.format(isCurrentYear ? 'MMMM' : 'MMMM YYYY')
	if (dateObj.isToday()) return __('Today')
	if (dateObj.isYesterday()) return __('Yesterday')
	return dateObj.format(isCurrentYear ? 'D MMMM' : 'D MMMM YYYY')
}

export const formatBytes = (bytes: number) => {
	if (!+bytes) return '0 Bytes'

	const k = 1024
	const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']

	const i = Math.floor(Math.log(bytes) / Math.log(k))

	return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

export const extractNameFromEmail = (email: string) =>
	email
		.split('@')[0]
		.replace(/[._-]/g, ' ')
		.replace(/\b\w/g, (c) => c.toUpperCase())

export const getRepeatFrequencyOptions = (interval: number) => [
	{ label: interval === 1 ? __('Year') : __('Years'), value: 'yearly' },
	{ label: interval === 1 ? __('Month') : __('Months'), value: 'monthly' },
	{ label: interval === 1 ? __('Week') : __('Weeks'), value: 'weekly' },
	{ label: interval === 1 ? __('Day') : __('Days'), value: 'daily' },
]

export const getRepeatMessage = (recurrenceRule: RecurrenceRule) => {
	const message = __('Every {0} {1}', [
		recurrenceRule.interval === 1 ? '' : recurrenceRule.interval,
		getRepeatFrequencyOptions(recurrenceRule.interval)
			.find((option) => option.value === recurrenceRule.frequency)!
			.label.toLowerCase(),
	])

	const suffix =
		getByDayMessage(recurrenceRule.byDay) || getByMonthDayMessage(recurrenceRule.byMonthDay)

	const fullMessage = `${message}${suffix}`

	if (recurrenceRule?.until)
		return __('{0} until {1}', [
			fullMessage,
			dayjs(recurrenceRule.until).format('MMM DD, YYYY'),
		])
	if (recurrenceRule?.count) return __('{0}, {1} times', [fullMessage, recurrenceRule.count])

	return fullMessage
}

interface RecurrenceRule {
	frequency: 'daily' | 'weekly' | 'monthly' | 'yearly'
	interval: number
	byDay?: { day: string; nthOfPeriod?: number }[]
	byMonthDay?: number[]
	until?: string
	count?: number
}
