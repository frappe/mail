import frappeUIPreset from 'frappe-ui/src/tailwind/preset'

export default {
	presets: [frappeUIPreset],
	content: [
		'./index.html',
		'./src/**/*.{vue,js,ts,jsx,tsx}',
		'./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}',
	],
	theme: {
		extend: {
			strokeWidth: {
				1.5: '1.5',
			},
			boxShadow: {
				'elevation-light-md':
					'0 0 1.5px 0 rgba(0, 0, 0, 0.15), 0 0 6px 2px rgba(0, 0, 0, 0.03), 0 6px 12px -2px rgba(0, 0, 0, 0.12)',
			},
		},
	},
	plugins: [],
}
