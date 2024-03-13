from frappe import _


def get_data():
	return {
		"fieldname": "server",
		"non_standard_fieldnames": {
			"Mail Domain": "outgoing_server",
		},
		"transactions": [
			{
				"items": [
					"Mail Domain",
					"Incoming Mail",
					"Outgoing Mail",
					"Mail Agent Job",
				]
			}
		],
	}
