const { light } = require('./app/theme/colors')

/** @type {import('tailwindcss').Config} */
module.exports = {
	content: ['./app/**/*.{vue,ts,js}'],
	theme: {
		// NativeScript does not support rem — use px values directly
		borderRadius: {
			none: '0',
			sm: '4',
			DEFAULT: '8',
			md: '10',
			lg: '12',
			xl: '16',
			'2xl': '20',
			full: '9999',
		},
		fontSize: {
			'2xs': ['11'],
			xs: ['12'],
			sm: ['13'],
			base: ['14'],
			lg: ['16'],
			xl: ['18'],
			'2xl': ['20'],
			'3xl': ['24'],
		},
		extend: {
			colors: {
				...light,
			},
			spacing: {
				4.5: '18',
				5.5: '22',
				6.5: '26',
				7.5: '30',
				8.5: '34',
				9.5: '38',
			},
		},
	},
	plugins: [require('@nativescript/tailwind')],
}
