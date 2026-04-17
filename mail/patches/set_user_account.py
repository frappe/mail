import frappe
from frappe.query_builder import Case

from mail.utils.user import get_user_personal_account

DOCTYPES = [
	"Mail Exchange",
	"Mail Queue",
	"Mail Sync History",
	"Mailbox Settings",
]


def execute() -> None:
	cached_user_accounts = {}

	for doctype in DOCTYPES:
		try:
			DOCTYPE = frappe.qb.DocType(doctype)
			USER_SETTINGS = frappe.qb.DocType("User Settings")
			users = (
				frappe.qb.from_(DOCTYPE)
				.join(USER_SETTINGS)
				.on(DOCTYPE.user == USER_SETTINGS.user)
				.select(DOCTYPE.user)
				.distinct()
				.where(
					(DOCTYPE.user.isnotnull())
					& (DOCTYPE.account.isnull())
					& (USER_SETTINGS.username.isnotnull())
				)
			).run(pluck="user")

			if not users:
				continue

			user_to_account = {}

			for user in users:
				if user not in cached_user_accounts:
					cached_user_accounts[user] = get_user_personal_account(user, raise_exception=False)

				account = cached_user_accounts[user]
				if account:
					user_to_account[user] = account

			if not user_to_account:
				continue

			case_stmt = Case()
			for user, account in user_to_account.items():
				case_stmt = case_stmt.when(DOCTYPE.user == user, account)

			(
				frappe.qb.update(DOCTYPE)
				.set(DOCTYPE.account, case_stmt)
				.where((DOCTYPE.user.isin(list(user_to_account.keys()))) & (DOCTYPE.account.isnull()))
			).run()

		except Exception as e:
			frappe.log_error(message=str(e), title=f"Error while setting user account for {doctype}")
