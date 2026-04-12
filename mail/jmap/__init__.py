from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from mail.jmap.connection import JMAPConnection, JMAPConnectionInfo
from mail.jmap.services.blob.blob import BlobService
from mail.jmap.services.calendars.calendar import CalendarService
from mail.jmap.services.calendars.calendar_event import CalendarEventService
from mail.jmap.services.calendars.calendar_event_notification import CalendarEventNotificationService
from mail.jmap.services.calendars.participant_identity import ParticipantIdentityService
from mail.jmap.services.contacts.address_book import AddressBookService
from mail.jmap.services.contacts.contact_card import ContactCardService
from mail.jmap.services.core import CoreService
from mail.jmap.services.mail.email import EmailService
from mail.jmap.services.mail.identity import IdentityService
from mail.jmap.services.mail.mailbox import MailboxService
from mail.jmap.services.mail.push_subscription import PushSubscriptionService
from mail.jmap.services.mail.submission.email_submission import EmailSubmissionService
from mail.jmap.services.mail.thread import ThreadService
from mail.jmap.services.principals.principal import PrincipalService
from mail.jmap.services.quota.quota import QuotaService
from mail.jmap.services.sieve.sieve_script import SieveScriptService
from mail.jmap.services.vacationresponse.vacation_response import VacationResponseService
from mail.jmap.services.websocket.websocket import WebSocketService
from mail.utils import get_mail_config
from mail.utils.user import has_role
from mail.utils.validation import has_permission_for_user


def get_jmap_connection(user: str, ignore_permissions: bool = False, cache: bool = True) -> JMAPConnection:
	"""Returns a JMAPConnection instance for the specified user, with optional permission checks and caching."""

	def generator() -> JMAPConnection:
		settings = frappe.db.exists("User Settings", {"user": user, "username": ["!=", None]})
		if not settings:
			frappe.throw(_("User {0} does not have JMAP settings configured.").format(frappe.bold(user)))

		user_settings = frappe.get_lazy_doc("User Settings", settings)

		if frappe.db.get_value("Mail Tenant Member", {"user": user}, "tenant"):
			if user_settings.user != user_settings.username:
				frappe.throw(
					_(
						"JMAP username for tenant-bound user {0} must be the same as the system username."
					).format(frappe.bold(user)),
					frappe.ValidationError,
				)

		server_url = user_settings.server_url or get_mail_config().get("server_url")
		if not server_url:
			frappe.throw(
				_("Server URL must be set in either the user's settings or the site configuration."),
				frappe.ValidationError,
			)

		info = JMAPConnectionInfo(
			server_url, user_settings.username, user_settings.get_password("app_password")
		)
		return JMAPConnection(info)

	if not ignore_permissions:
		if not has_permission_for_user(user, raise_exception=False):
			frappe.throw(
				_("You do not have permission to access the JMAPConnection for user {0}.").format(
					frappe.bold(user)
				),
				frappe.PermissionError,
			)

	if not bool(frappe.db.get_value("User", user, "enabled")):
		frappe.throw(_("User {0} is disabled.").format(frappe.bold(user)))

	if not has_role(user, ["Mail User"]):
		frappe.throw(_("User {0} does not have the Mail User role.").format(frappe.bold(user)))

	if cache:
		return frappe.cache.hget("jmap:connection", user, generator)
	else:
		return generator()


def get_address_book_service(
	user: str, ignore_permissions: bool = False, cache: bool = True
) -> AddressBookService:
	"""Returns an instance of AddressBookService for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return AddressBookService(user, connection)


def get_core_service(user: str, ignore_permissions: bool = False, cache: bool = True) -> CoreService:
	"""Returns an instance of CoreService for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return CoreService(user, connection)


def get_blob_service(user: str, ignore_permissions: bool = False, cache: bool = True) -> BlobService:
	"""Returns an instance of BlobService for handling blob-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return BlobService(user, connection)


def get_calendar_event_notification_service(
	user: str, ignore_permissions: bool = False, cache: bool = True
) -> CalendarEventNotificationService:
	"""Returns an instance of CalendarEventNotificationService for handling calendar event notification-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return CalendarEventNotificationService(user, connection)


def get_calendar_event_service(
	user: str, ignore_permissions: bool = False, cache: bool = True
) -> CalendarEventService:
	"""Returns an instance of CalendarEventService for handling calendar event-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return CalendarEventService(user, connection)


def get_calendar_service(user: str, ignore_permissions: bool = False, cache: bool = True) -> CalendarService:
	"""Returns an instance of CalendarService for handling calendar-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return CalendarService(user, connection)


def get_contact_card_service(
	user: str, ignore_permissions: bool = False, cache: bool = True
) -> ContactCardService:
	"""Returns an instance of ContactCardService for handling contact card-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return ContactCardService(user, connection)


def get_email_service(user: str, ignore_permissions: bool = False, cache: bool = True) -> EmailService:
	"""Returns an instance of EmailService for handling email-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return EmailService(user, connection)


def get_email_submission_service(
	user: str, ignore_permissions: bool = False, cache: bool = True
) -> EmailSubmissionService:
	"""Returns an instance of EmailSubmissionService for handling email submission-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return EmailSubmissionService(user, connection)


def get_identity_service(user: str, ignore_permissions: bool = False, cache: bool = True) -> IdentityService:
	"""Returns an instance of IdentityService for handling identity-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return IdentityService(user, connection)


def get_mailbox_service(user: str, ignore_permissions: bool = False, cache: bool = True) -> MailboxService:
	"""Returns an instance of MailboxService for handling mailbox-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return MailboxService(user, connection)


def get_participant_identity_service(
	user: str, ignore_permissions: bool = False, cache: bool = True
) -> ParticipantIdentityService:
	"""Returns an instance of ParticipantIdentityService for handling participant identity-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return ParticipantIdentityService(user, connection)


def get_principal_service(
	user: str, ignore_permissions: bool = False, cache: bool = True
) -> PrincipalService:
	"""Returns an instance of PrincipalService for handling principal-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return PrincipalService(user, connection)


def get_push_subscription_service(
	user: str, ignore_permissions: bool = False, cache: bool = True
) -> PushSubscriptionService:
	"""Returns an instance of PushSubscriptionService for handling push subscription-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return PushSubscriptionService(user, connection)


def get_quota_service(user: str, ignore_permissions: bool = False, cache: bool = True) -> QuotaService:
	"""Returns an instance of QuotaService for handling quota-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return QuotaService(user, connection)


def get_sieve_script_service(
	user: str, ignore_permissions: bool = False, cache: bool = True
) -> SieveScriptService:
	"""Returns an instance of SieveScriptService for handling sieve script-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return SieveScriptService(user, connection)


def get_thread_service(user: str, ignore_permissions: bool = False, cache: bool = True) -> ThreadService:
	"""Returns an instance of ThreadService for handling thread-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return ThreadService(user, connection)


def get_vacation_response_service(
	user: str, ignore_permissions: bool = False, cache: bool = True
) -> VacationResponseService:
	"""Returns an instance of VacationResponseService for handling vacation response-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return VacationResponseService(user, connection)


def get_websocket_service(
	user: str, ignore_permissions: bool = False, cache: bool = True
) -> WebSocketService:
	"""Returns an instance of WebSocketService for handling WebSocket-related operations for the specified user."""

	connection = get_jmap_connection(user, ignore_permissions=ignore_permissions, cache=cache)
	return WebSocketService(user, connection)


def invalidate_jmap_cache(user: str) -> None:
	"""Invalidates all JMAP-related caches for the specified user."""

	invalidate_jmap_connection_cache(user)
	invalidate_jmap_identities_cache(user)
	invalidate_jmap_mailboxes_cache(user)


def invalidate_jmap_connection_cache(user: str) -> None:
	"""Invalidates the JMAP connection cache for the specified user."""

	frappe.cache.hdel("jmap:connection", user)


def invalidate_jmap_identities_cache(user: str) -> None:
	"""Invalidates the JMAP identities cache for the specified user."""

	IdentityService.invalidate_cache(user, key="identities")
	frappe.cache.hdel(f"user|{user}", "emails")


def invalidate_jmap_mailboxes_cache(user: str) -> None:
	"""Invalidates the JMAP mailboxes cache for the specified user."""

	IdentityService.invalidate_cache(user, key="mailboxes")


def get_identities(user: str) -> list[dict]:
	"""Returns the list of identities for the specified user."""

	connection = get_jmap_connection(user)
	service = IdentityService(user, connection)

	identities = [
		{
			"name": f"{user}|{i['id']}",
			"user": user,
			"id": i["id"],
			"_name": i["name"],
			"email": i["email"].lower(),
			"bcc": [{"display_name": b["name"], "email": b["email"].lower()} for b in i.get("bcc") or []],
			"reply_to": [
				{"display_name": r["name"], "email": r["email"].lower()} for r in i.get("replyTo") or []
			],
			"html_signature": i["htmlSignature"],
			"text_signature": i["textSignature"],
			"may_delete": cint(i["mayDelete"]),
		}
		for i in service.identities
	]

	return identities


def get_identity_id_by_email(user: str, email: str, raise_exception: bool = False) -> str | None:
	"""Returns the identity ID for the specified email address, or None if not found."""

	connection = get_jmap_connection(user)
	service = IdentityService(user, connection)
	return service.get_identity_id_by_email(email, raise_exception=raise_exception)


def get_mailboxes(user: str) -> list[dict]:
	"""Returns the list of mailboxes for the specified user."""

	connection = get_jmap_connection(user)
	service = MailboxService(user, connection)

	mailboxes = [
		{
			"name": f"{user}|{m['id']}",
			"user": user,
			"id": m["id"],
			"role": m["role"],
			"_name": m["name"],
			"_parent": f"{user}|{m['parentId']}" if m.get("parentId") else None,
			"parent_id": m["parentId"],
			"subscribed": m["isSubscribed"],
		}
		for m in service.mailboxes
	]

	return mailboxes


def get_mailbox_id_by_role(
	user: str, role: str, create_if_not_exists: bool = False, raise_exception: bool = False
) -> str | None:
	"""Returns the mailbox ID for the specified role, or None if not found. Optionally creates the mailbox if it does not exist."""

	connection = get_jmap_connection(user)
	service = MailboxService(user, connection)
	return service.get_mailbox_id_by_role(
		role, create_if_not_exists=create_if_not_exists, raise_exception=raise_exception
	)


def get_mailbox_role_by_id(user: str, id: str, raise_exception: bool = False) -> str | None:
	"""Returns the mailbox role for the specified mailbox ID, or None if not found."""

	connection = get_jmap_connection(user)
	service = MailboxService(user, connection)
	return service.get_mailbox_role_by_id(id, raise_exception=raise_exception)


def get_mailbox_name_by_id(user: str, id: str, raise_exception: bool = False) -> str | None:
	"""Returns the mailbox name for the specified mailbox ID, or None if not found."""

	connection = get_jmap_connection(user)
	service = MailboxService(user, connection)
	return service.get_mailbox_name_by_id(id, raise_exception=raise_exception)


def get_default_address_book_id(user: str, raise_exception: bool = False) -> str | None:
	"""Returns the ID of the default address book for the specified user, or None if not found."""

	connection = get_jmap_connection(user)
	service = AddressBookService(user, connection)
	return service.get_default(raise_exception=raise_exception)


def get_default_calendar_id(user: str, raise_exception: bool = False) -> str | None:
	"""Returns the ID of the default calendar for the specified user, or None if not found."""

	connection = get_jmap_connection(user)
	service = CalendarService(user, connection)
	return service.get_default(raise_exception=raise_exception)


@frappe.whitelist()
def get_mailboxes_for_user(user: str) -> list[dict]:
	"""Returns the list of mailboxes for the specified user."""

	has_permission_for_user(user)
	return get_mailboxes(user)


@frappe.whitelist()
def get_mailbox_id_for_user(
	user: str, role: str, create_if_not_exists: bool = False, raise_exception: bool = False
) -> str | None:
	"""Returns the mailbox ID for the specified role, or None if not found. Optionally creates the mailbox if it does not exist."""

	has_permission_for_user(user)
	return get_mailbox_id_by_role(
		user, role, create_if_not_exists=create_if_not_exists, raise_exception=raise_exception
	)


@frappe.whitelist()
def get_mailbox_name_for_user(user: str, id: str, raise_exception: bool = False) -> str | None:
	"""Returns the mailbox name for the specified mailbox ID, or None if not found."""

	has_permission_for_user(user)
	return get_mailbox_name_by_id(user, id, raise_exception=raise_exception)


@frappe.whitelist()
def make_jmap_request(user: str, capabilities: list[str], method_calls: list[list]) -> Any:
	"""Makes a JMAP request on behalf of the specified user, with the given method calls."""

	has_permission_for_user(user)

	connection = get_jmap_connection(user)
	service = CoreService(user, connection)

	return service._call(capabilities, method_calls)
