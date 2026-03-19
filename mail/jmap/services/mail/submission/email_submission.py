from typing import ClassVar

from mail import __version__
from mail.jmap.models import EmailCreateModel
from mail.jmap.services.core import CallIdGenerator, CoreService
from mail.jmap.services.mail.identity import IdentityService
from mail.jmap.services.mail.mailbox import MailboxService


class EmailSubmissionService(CoreService):
	"""Service for handling email submission-related functionality based on the JMAP server capabilities."""

	type: ClassVar[str] = "EmailSubmission"
	capabilities: ClassVar[list[str]] = [
		"urn:ietf:params:jmap:core",
		"urn:ietf:params:jmap:mail",
		"urn:ietf:params:jmap:submission",
	]

	def __post_init__(self) -> None:
		"""Post-initialization to check if the JMAP server supports the Mail and EmailSubmission capability and raise an error if not."""

		super().__post_init__()

		if "urn:ietf:params:jmap:mail" not in self.connection.capabilities:
			raise NotImplementedError("The JMAP server does not support the Mail capability.")

		if "urn:ietf:params:jmap:submission" not in self.connection.capabilities:
			raise NotImplementedError("The JMAP server does not support the EmailSubmission capability.")

	@property
	def primary_account_id(self) -> str:
		"""Returns the primary account ID for the logged-in user."""

		return self.connection.primary_accounts["urn:ietf:params:jmap:submission"]

	def _create(
		self, emails: list[EmailCreateModel], draft_refs: dict[str, str], call_id_gen: CallIdGenerator
	) -> list:
		"""Creates email submissions for the given list of EmailCreateModel instances and returns the method calls for the JMAP request."""

		method_calls = []

		identity_service = IdentityService(self.user, self.connection)
		mailbox_service = MailboxService(self.user, self.connection)

		draft_mailbox_id = mailbox_service.get_mailbox_id_by_role(
			"drafts", create_if_not_exists=True, raise_exception=True
		)
		sent_mailbox_id = mailbox_service.get_mailbox_id_by_role(
			"sent", create_if_not_exists=True, raise_exception=True
		)

		create_payload = {}
		on_success_update = {}
		on_success_destroy = []

		for email in emails:
			if email.save_as_draft:
				continue

			# -----------------------------
			# Get Identity
			# -----------------------------

			identity_id = identity_service.get_identity_id_by_email(email.from_email, raise_exception=True)

			# -----------------------------
			# CREATE Submission
			# -----------------------------

			draft_ref = draft_refs[email.creation_id]
			submit_ref = f"submit-{email.creation_id}"

			create_payload[submit_ref] = {
				"identityId": identity_id,
				"emailId": f"#{draft_ref}",
				"envelope": {
					"mailFrom": {
						"email": email.from_email,
						"parameters": {
							"RET": "FULL",
							"ENVID": email.creation_id,
							"MT-PRIORITY": str(email.priority),
						},
					},
					"rcptTo": [
						{
							"email": rcpt,
							"parameters": {
								"NOTIFY": "DELAY,FAILURE",
								"ORCPT": f"rfc822;{rcpt}",
							},
						}
						for rcpt in sorted({r.email for r in email.recipients})
					],
				},
			}

			# -----------------------------
			# Success Handlers
			# -----------------------------

			if email.destroy_after_submit:
				# No Mailbox updates, just destroy the draft email after successful submission.
				on_success_destroy.append(f"#{submit_ref}")

			else:
				# Move the draft email to the Sent mailbox and update keywords after successful submission.
				on_success_update[f"#{submit_ref}"] = {
					f"mailboxIds/{draft_mailbox_id}": None,
					f"mailboxIds/{sent_mailbox_id}": True,
					"keywords/$draft": None,
					"keywords/$seen": True,
				}

			# -----------------------------
			# Forward / Reply Keywords
			# -----------------------------

			for target_id, keyword in [
				(email.forwarded_id, "$forwarded"),
				(email.reply_to_id, "$answered"),
			]:
				if target_id:
					on_success_update.setdefault(target_id, {})[f"keywords/{keyword}"] = True

		if create_payload:
			payload = {
				"accountId": self.primary_account_id,
				"create": create_payload,
			}

			if on_success_update:
				payload["onSuccessUpdateEmail"] = on_success_update

			if on_success_destroy:
				payload["onSuccessDestroyEmail"] = on_success_destroy

			method_calls.append(["EmailSubmission/set", payload, call_id_gen.next()])

		return method_calls
