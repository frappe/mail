from frappe import _


def get_data():
	return {
		"fieldname": "server",
		"non_standard_fieldnames": {
			"Mail Domain": "outgoing_server",
		},
		"transactions": [{"items": ["Mail Domain", "Mail Agent Job", "Outgoing Mail"]}],
	}
