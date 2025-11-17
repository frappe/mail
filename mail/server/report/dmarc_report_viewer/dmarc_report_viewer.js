// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports['DMARC Report Viewer'] = {
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data)

		if (['spf_result', 'dkim_result', 'result'].includes(column.fieldname)) {
			value =
				data[column.fieldname] === 'PASS'
					? `<span style='color:green'>${value}</span>`
					: `<span style='color:red'>${value}</span>`
		} else if (column.fieldname === 'source_ip' && data[column.fieldname]) {
			value = data['is_local_ip']
				? `<span style='color:green'>${value}</span>`
				: `<span style='color:black'>${value}</span>`
		}

		return value
	},

	filters: [
		{
			fieldname: 'cluster',
			label: __('Cluster'),
			fieldtype: 'Link',
			options: 'Mail Cluster',
			reqd: 1,
		},
	],
}
