from frappe import _


def get_data():
	return {
		"fieldname": "sender",
		"transactions": [
			{
				"label": _("Reference"),
				"items": ["FM Queue"],
			}
		],
	}
