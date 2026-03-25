// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Calendar Event', {
	before_load: (frm) => {
		const update_tz_options = () => {
			frm.fields_dict.time_zone.set_data(frappe.all_timezones)
			frm.fields_dict.recurrence_id_time_zone.set_data(frappe.all_timezones)
		}

		if (!frappe.all_timezones) {
			frappe.call({
				method: 'frappe.core.doctype.user.user.get_timezones',
				callback: function (r) {
					frappe.all_timezones = r.message.timezones
					update_tz_options()
				},
			})
		} else {
			update_tz_options()
		}
	},

	refresh(frm) {
		frm.trigger('set_queries')
	},

	set_queries(frm) {
		frm.set_query('calendar', 'calendars', () => ({
			query: 'mail.utils.query.get_user_calendars',
			filters: {
				user: frm.doc.user,
			},
		}))
	},
})
