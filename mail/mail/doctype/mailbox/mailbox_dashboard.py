from frappe import _


def get_data():
	return {
		"fieldname": "mailbox",
		"non_standard_fieldnames": {"Incoming Mail": "receiver", "Outgoing Mail": "sender"},
		"transactions": [
			{
				"label": _("Reference"),
				"items": ["Mail Alias", "Incoming Mail", "Outgoing Mail"],
			}
		],
	}
