const { light } = require('./app/theme/colors')

/** @type {import('tailwindcss').Config} */
module.exports = {
	content: ['./app/**/*.{vue,ts,js}'],
	theme: {
		extend: {
			colors: {
				...light,
			},
			// Default border color, matching frappe-ui's webmail (its plugin sets
			// borderColor.DEFAULT = var(--outline-gray-1)).
			borderColor: {
				DEFAULT: light['outline-gray-1'],
			},
			fontFamily: {
				lucide: ['lucide'],
			},
		},
	},
	plugins: [require('@nativescript/tailwind')],
}
