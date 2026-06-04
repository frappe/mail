const { light } = require('./app/theme/colors')

/** @type {import('tailwindcss').Config} */
module.exports = {
	content: ['./app/**/*.{vue,ts,js}'],
	theme: {
		extend: {
			colors: {
				...light,
			},
			fontFamily: {
				lucide: ['lucide'],
			},
		},
	},
	plugins: [require('@nativescript/tailwind')],
}
