from frappe import _


def get_data():
	return {
		"fieldname": "server",
		"non_standard_fieldnames": {
			"FM Domain": "outgoing_server",
		},
		"transactions": [{"items": ["FM Domain", "FM Agent Job", "FM Outgoing Email"]}],
	}
