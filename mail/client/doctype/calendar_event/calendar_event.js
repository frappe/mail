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

	user(frm) {
		if (frm.doc.user) {
			frappe.call({
				method: 'mail.jmap.get_user_accounts',
				args: {
					user: frm.doc.user,
				},
				callback: (r) => {
					if (r.message) {
						frm.set_df_property('account', 'options', r.message)
						frm.refresh_field('account')
					}
				},
			})
		} else {
			frm.set_df_property('account', 'options', [])
			frm.refresh_field('account')
		}
	},

	set_queries(frm) {
		frm.set_query('calendar', 'calendars', () => ({
			query: 'mail.utils.query.get_account_calendars',
			filters: {
				account: frm.doc.account,
			},
		}))
	},
})
