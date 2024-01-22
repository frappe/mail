from frappe import _


def get_data():
	return {
		"fieldname": "server",
		"non_standard_fieldnames": {
			"FM Domain": "outgoing_server",
			"FM Outgoing Email": "server",
		},
		"transactions": [{"items": ["FM Domain", "FM Outgoing Email"]}],
	}
