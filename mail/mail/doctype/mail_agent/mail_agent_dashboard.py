from frappe import _


def get_data():
	return {
		"fieldname": "agent",
		"non_standard_fieldnames": {
			"Mail Domain": "outgoing_agent",
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
