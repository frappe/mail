import frappe
from frappe import _

# Redirect URI registered in the mobile app's Info.plist (iOS) and AndroidManifest.xml (Android).
MOBILE_REDIRECT_URI = "com.frappe.mail://oauth"


# Guest access is intentional: the mobile app fetches the public OAuth client_id
# before login to begin the auth flow. Only non-sensitive public config is returned.
@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
def get_client_id() -> dict:
	"""Returns the OAuth2 client ID and site metadata needed by the mobile app.

	Called before login — no authentication required. Returns an error if the
	site admin has not yet configured a mobile OAuth client.
	"""
	client_id = frappe.db.get_single_value("Mail Settings", "mobile_oauth_client")
	if not client_id:
		frappe.throw(
			_(
				"Mobile OAuth client is not configured. "
				"Ask your site administrator to set it up in Mail Settings → Mobile."
			),
			frappe.DoesNotExistError,
		)

	app_name = frappe.db.get_single_value("Website Settings", "app_name") or "Frappe Mail"
	logo = frappe.db.get_single_value("Website Settings", "favicon") or "/assets/mail/images/mail-logo.svg"

	return {
		"client_id": client_id,
		"app_name": app_name,
		"logo": logo,
		"sitename": frappe.local.site,
	}


@frappe.whitelist(methods=["POST"])
def create_oauth_client() -> dict:
	"""Creates (or updates) the OAuth2 client for the Frappe Mail mobile app.

	Must be called by a System Manager. Stores the resulting client ID in
	Mail Settings so that get_client_id() can return it to the mobile app.
	"""
	if not frappe.has_permission("Mail Settings", "write"):
		frappe.throw(
			_("You do not have permission to configure mobile OAuth settings."), frappe.PermissionError
		)

	existing_client_id = frappe.db.get_single_value("Mail Settings", "mobile_oauth_client")

	if existing_client_id and frappe.db.exists("OAuth Client", existing_client_id):
		oauth_client = frappe.get_doc("OAuth Client", existing_client_id)
	else:
		oauth_client = frappe.new_doc("OAuth Client")

	oauth_client.app_name = "Frappe Mail Mobile"
	oauth_client.scopes = "all openid"
	oauth_client.redirect_uris = MOBILE_REDIRECT_URI
	oauth_client.default_redirect_uri = MOBILE_REDIRECT_URI
	oauth_client.grant_type = "Authorization Code"
	oauth_client.response_type = "Code"
	oauth_client.skip_authorization = 1
	oauth_client.save(ignore_permissions=True)

	frappe.db.set_single_value("Mail Settings", "mobile_oauth_client", oauth_client.name)

	return {
		"client_id": oauth_client.name,
		"message": _("Mobile OAuth client configured successfully."),
	}
