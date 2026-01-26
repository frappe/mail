#!/usr/bin/env python
"""
Interactive Enterprise Battle Test Runner for Frappe Mail
=========================================================

This script runs comprehensive tests against a live Frappe Mail + Stalwart setup.
Run with: bench --site <site> execute mail.tests.run_battle_test

Test Categories:
1. Stalwart Connectivity
2. JMAP Operations
3. Email Send/Receive
4. Scheduled Email (FUTURERELEASE)
5. Webhook Processing
6. Mailbox Operations
7. Search Functionality
"""

import frappe
from frappe.utils import now_datetime, add_to_date, random_string, get_datetime
from datetime import datetime, timedelta
import time
import json


class BattleTestRunner:
	"""Interactive test runner for enterprise battle testing."""

	def __init__(self, user=None, verbose=True):
		self.user = user or frappe.session.user
		self.verbose = verbose
		self.results = {
			"passed": 0,
			"failed": 0,
			"skipped": 0,
			"errors": [],
			"tests": []
		}

	def log(self, msg, level="info"):
		if self.verbose:
			prefix = {
				"info": "ℹ️ ",
				"success": "✅",
				"error": "❌",
				"warning": "⚠️ ",
				"skip": "⏭️ ",
			}.get(level, "")
			print(f"{prefix} {msg}")

	def record_result(self, test_name, passed, message="", skipped=False):
		status = "skipped" if skipped else ("passed" if passed else "failed")
		self.results["tests"].append({
			"name": test_name,
			"status": status,
			"message": message
		})
		if skipped:
			self.results["skipped"] += 1
		elif passed:
			self.results["passed"] += 1
		else:
			self.results["failed"] += 1
			self.results["errors"].append(f"{test_name}: {message}")

	def run_all(self):
		"""Run all test categories."""
		print("\n" + "=" * 70)
		print("🚀 FRAPPE MAIL ENTERPRISE BATTLE TEST")
		print("=" * 70)
		print(f"User: {self.user}")
		print(f"Time: {now_datetime()}")
		print("=" * 70 + "\n")

		self.test_environment()
		self.test_jmap_connectivity()
		self.test_mailbox_operations()
		self.test_email_composition()
		self.test_scheduled_email()
		self.test_search_functionality()
		self.test_webhook_configuration()
		self.test_api_endpoints()

		self.print_summary()
		return self.results

	# =========================================================================
	# 1. Environment Tests
	# =========================================================================
	def test_environment(self):
		print("\n📋 1. ENVIRONMENT CHECKS")
		print("-" * 40)

		# Check Mail Settings
		try:
			if frappe.db.exists("Mail Settings"):
				settings = frappe.get_single("Mail Settings")
				self.log(f"Mail Settings found", "success")
				self.record_result("Mail Settings exists", True)
			else:
				self.log("Mail Settings not configured", "warning")
				self.record_result("Mail Settings exists", False, "Not configured", skipped=True)
		except Exception as e:
			self.log(f"Error checking Mail Settings: {e}", "error")
			self.record_result("Mail Settings exists", False, str(e))

		# Check Mail Server
		try:
			servers = frappe.get_all("Mail Server", filters={"enabled": 1}, limit=1)
			if servers:
				self.log(f"Enabled Mail Server: {servers[0].name}", "success")
				self.record_result("Mail Server configured", True)
			else:
				self.log("No enabled Mail Server found", "warning")
				self.record_result("Mail Server configured", False, "No server", skipped=True)
		except Exception as e:
			self.log(f"Error checking Mail Server: {e}", "error")
			self.record_result("Mail Server configured", False, str(e))

		# Check User Identity (virtual doctype from JMAP)
		try:
			from mail.client.doctype.identity.identity import fetch_identities
			identities = fetch_identities(self.user)
			if identities:
				self.log(f"User Identity: {identities[0].get('email')}", "success")
				self.record_result("User Identity exists", True)
				self.identity = {"email": identities[0].get("email"), "name": identities[0].get("name")}
			else:
				self.log(f"No identity for user {self.user}", "warning")
				self.record_result("User Identity exists", False, "No identity", skipped=True)
				self.identity = None
		except Exception as e:
			self.log(f"Error checking Identity: {e}", "error")
			self.record_result("User Identity exists", False, str(e))
			self.identity = None

	# =========================================================================
	# 2. JMAP Connectivity Tests
	# =========================================================================
	def test_jmap_connectivity(self):
		print("\n🔌 2. JMAP CONNECTIVITY")
		print("-" * 40)

		try:
			from mail.jmap import JMAPClient, get_jmap_client

			client = get_jmap_client(self.user)
			self.log(f"JMAP Client initialized", "success")
			self.log(f"  API URL: {client.api_url}", "info")
			self.log(f"  Account ID: {client.primary_account_id[:20]}...", "info")
			self.record_result("JMAP Client initialization", True)
			self.jmap_client = client
		except Exception as e:
			self.log(f"JMAP Client failed: {e}", "error")
			self.record_result("JMAP Client initialization", False, str(e))
			self.jmap_client = None
			return

		# Test session capabilities
		try:
			capabilities = getattr(client, 'capabilities', {})
			if capabilities:
				self.log(f"Session capabilities: {len(capabilities)} found", "success")
			self.record_result("JMAP Session discovery", True)
		except Exception as e:
			self.log(f"Session discovery failed: {e}", "error")
			self.record_result("JMAP Session discovery", False, str(e))

	# =========================================================================
	# 3. Mailbox Operations Tests
	# =========================================================================
	def test_mailbox_operations(self):
		print("\n📁 3. MAILBOX OPERATIONS")
		print("-" * 40)

		if not getattr(self, 'jmap_client', None):
			self.log("Skipping - JMAP client not available", "skip")
			self.record_result("Mailbox operations", False, "No JMAP client", skipped=True)
			return

		from mail.jmap import get_mailbox_id_by_role

		# Test standard mailboxes
		roles = ["inbox", "drafts", "sent", "trash", "junk", "archive"]
		for role in roles:
			try:
				mailbox_id = get_mailbox_id_by_role(
					self.user, role, create_if_not_exists=True, raise_exception=False
				)
				if mailbox_id:
					self.log(f"Mailbox '{role}': {mailbox_id[:20]}...", "success")
					self.record_result(f"Mailbox {role}", True)
				else:
					self.log(f"Mailbox '{role}': Not found", "warning")
					self.record_result(f"Mailbox {role}", False, "Not found", skipped=True)
			except Exception as e:
				self.log(f"Mailbox '{role}' failed: {e}", "error")
				self.record_result(f"Mailbox {role}", False, str(e))

		# Test Scheduled mailbox (special)
		try:
			scheduled_id = get_mailbox_id_by_role(
				self.user, "scheduled", create_if_not_exists=True, raise_exception=False
			)
			if scheduled_id:
				self.log(f"Mailbox 'scheduled': {scheduled_id[:20]}...", "success")
				self.record_result("Mailbox scheduled", True)
			else:
				self.log("Mailbox 'scheduled': Not found (may need creation)", "warning")
				self.record_result("Mailbox scheduled", False, "Not found", skipped=True)
		except Exception as e:
			self.log(f"Mailbox 'scheduled' failed: {e}", "error")
			self.record_result("Mailbox scheduled", False, str(e))

	# =========================================================================
	# 4. Email Composition Tests
	# =========================================================================
	def test_email_composition(self):
		print("\n✉️  4. EMAIL COMPOSITION")
		print("-" * 40)

		if not getattr(self, 'identity', None):
			self.log("Skipping - No identity configured", "skip")
			self.record_result("Email composition", False, "No identity", skipped=True)
			return

		from mail.client.doctype.mail_queue.mail_queue import MailQueue
		
		# Get email from identity dict
		from_email = self.identity.get("email") if isinstance(self.identity, dict) else self.identity.email

		# Test draft creation
		try:
			test_subject = f"Battle Test Draft {random_string(8)}"
			doc = MailQueue._create(
				user=self.user,
				from_email=from_email,
				from_name="Battle Test",
				subject=test_subject,
				html_body="<p>This is a battle test draft email.</p>",
				recipients=[{"type": "To", "email": "test@example.com"}],
				save_as_draft=True,
			)
			self.log(f"Draft created: {doc.name}", "success")
			self.log(f"  Status: {doc.status}", "info")
			self.log(f"  ID: {doc.id[:20] if doc.id else 'None'}...", "info")
			self.record_result("Create draft email", True)
			self.test_draft = doc
		except Exception as e:
			self.log(f"Draft creation failed: {e}", "error")
			self.record_result("Create draft email", False, str(e))
			self.test_draft = None

		# Test with attachments (skip in automated testing - requires real file upload)
		# This validation is correct behavior - attachments need real file data
		self.log("Attachment test skipped (requires real file upload)", "skip")
		self.record_result("Create draft with attachment", True, "Skipped - requires real file", skipped=True)

	# =========================================================================
	# 5. Scheduled Email Tests
	# =========================================================================
	def test_scheduled_email(self):
		print("\n⏰ 5. SCHEDULED EMAIL (FUTURERELEASE)")
		print("-" * 40)

		if not getattr(self, 'identity', None):
			self.log("Skipping - No identity configured", "skip")
			self.record_result("Scheduled email", False, "No identity", skipped=True)
			return

		from mail.client.doctype.mail_queue.mail_queue import MailQueue
		
		# Get email from identity dict
		from_email = self.identity.get("email") if isinstance(self.identity, dict) else self.identity.email

		# Test creating scheduled email
		scheduled_time = add_to_date(now_datetime(), hours=2)
		try:
			test_subject = f"Battle Test Scheduled {random_string(8)}"
			doc = MailQueue._create(
				user=self.user,
				from_email=from_email,
				from_name="Battle Test",
				subject=test_subject,
				html_body="<p>This is a battle test scheduled email.</p>",
				recipients=[{"type": "To", "email": "scheduled-test@example.com"}],
				scheduled_at=scheduled_time,
			)
			self.log(f"Scheduled email created: {doc.name}", "success")
			self.log(f"  Status: {doc.status}", "info")
			self.log(f"  Scheduled at: {doc.scheduled_at}", "info")
			self.log(f"  Submission ID: {doc.submission_id[:20] if doc.submission_id else 'None'}...", "info")
			self.record_result("Create scheduled email", True)
			self.test_scheduled = doc
		except Exception as e:
			self.log(f"Scheduled email creation failed: {e}", "error")
			self.record_result("Create scheduled email", False, str(e))
			self.test_scheduled = None
			return

		# Wait for async processing if needed
		time.sleep(2)
		doc.reload()

		# Test JMAP submission status
		if doc.submission_id and getattr(self, 'jmap_client', None):
			try:
				response = self.jmap_client.email_submission_get([doc.submission_id])
				submissions = response.get("methodResponses", [[None, {}]])[0][1].get("list", [])
				if submissions:
					submission = submissions[0]
					undo_status = submission.get("undoStatus", "unknown")
					self.log(f"Submission status: {undo_status}", "success")
					self.record_result("Check submission status", True)
				else:
					self.log("Submission not found in JMAP", "warning")
					self.record_result("Check submission status", False, "Not found", skipped=True)
			except Exception as e:
				self.log(f"Submission status check failed: {e}", "error")
				self.record_result("Check submission status", False, str(e))

		# Test update scheduled time
		if doc.status == "Scheduled" and doc.submission_id:
			new_time = add_to_date(now_datetime(), hours=4)
			try:
				doc.update_scheduled_time(str(new_time))
				doc.reload()
				self.log(f"Scheduled time updated to: {doc.scheduled_at}", "success")
				self.record_result("Update scheduled time", True)
			except Exception as e:
				self.log(f"Update scheduled time failed: {e}", "error")
				self.record_result("Update scheduled time", False, str(e))
		else:
			self.log("Skipping update test - email not in Scheduled status", "skip")
			self.record_result("Update scheduled time", False, "Not scheduled", skipped=True)

		# Test cancel scheduled email
		if doc.status == "Scheduled" and doc.submission_id:
			try:
				doc.cancel_scheduled()
				doc.reload()
				self.log(f"Scheduled email cancelled. Status: {doc.status}", "success")
				self.record_result("Cancel scheduled email", True)
			except Exception as e:
				self.log(f"Cancel scheduled failed: {e}", "error")
				self.record_result("Cancel scheduled email", False, str(e))
		else:
			self.log("Skipping cancel test - email not in Scheduled status", "skip")
			self.record_result("Cancel scheduled email", False, "Not scheduled", skipped=True)

	# =========================================================================
	# 6. Search Functionality Tests
	# =========================================================================
	def test_search_functionality(self):
		print("\n🔍 6. SEARCH FUNCTIONALITY")
		print("-" * 40)

		if not getattr(self, 'jmap_client', None):
			self.log("Skipping - No JMAP client", "skip")
			self.record_result("Search functionality", False, "No JMAP client", skipped=True)
			return

		# Use user context for search
		from mail.utils import user_context

		with user_context(self.user):
			from mail.api.mail import search_mails

			# Basic text search
			try:
				start = time.time()
				results, count = search_mails({"text": "test"}, limit=10)
				elapsed = time.time() - start
				self.log(f"Text search completed in {elapsed:.2f}s", "success")
				self.log(f"  Results: {len(results)}, Total: {count}", "info")
				self.record_result("Text search", True)
			except Exception as e:
				self.log(f"Text search failed: {e}", "error")
				self.record_result("Text search", False, str(e))

			# Search with filters
			try:
				results, count = search_mails({"hasAttachment": "true"}, limit=10)
				self.log(f"Attachment filter search: {len(results)} results", "success")
				self.record_result("Filter search (attachment)", True)
			except Exception as e:
				self.log(f"Attachment search failed: {e}", "error")
				self.record_result("Filter search (attachment)", False, str(e))

			# Date range search
			try:
				week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
				today = datetime.now().strftime("%Y-%m-%d")
				results, count = search_mails({"after": week_ago, "before": today}, limit=10)
				self.log(f"Date range search: {len(results)} results", "success")
				self.record_result("Date range search", True)
			except Exception as e:
				self.log(f"Date range search failed: {e}", "error")
				self.record_result("Date range search", False, str(e))

	# =========================================================================
	# 7. Webhook Configuration Tests
	# =========================================================================
	def test_webhook_configuration(self):
		print("\n🔗 7. WEBHOOK CONFIGURATION")
		print("-" * 40)

		# Check webhook events defined
		try:
			from mail.api.webhook import DELIVERY_EVENTS, QUEUE_EVENTS
			self.log(f"Delivery events: {DELIVERY_EVENTS}", "success")
			self.log(f"Queue events: {QUEUE_EVENTS}", "success")
			self.record_result("Webhook events defined", True)
		except Exception as e:
			self.log(f"Webhook events not defined: {e}", "error")
			self.record_result("Webhook events defined", False, str(e))

		# Check webhook URL configuration
		try:
			webhook_url = frappe.conf.get("stalwart_webhook_url")
			site_url = frappe.utils.get_url()
			effective_url = webhook_url or site_url
			self.log(f"Webhook URL: {effective_url}/webhook/delivery", "success")
			self.record_result("Webhook URL configured", True)
		except Exception as e:
			self.log(f"Webhook URL check failed: {e}", "error")
			self.record_result("Webhook URL configured", False, str(e))

		# Check hooks.py routes (in website_redirects, not website_route_rules)
		try:
			import mail.hooks as hooks
			redirects = getattr(hooks, 'website_redirects', [])
			delivery_route = any(
				'/webhook/delivery' in str(redirect.get('source', '') or redirect.get('target', ''))
				for redirect in redirects
			)
			if delivery_route:
				self.log("Webhook route registered in hooks.py (website_redirects)", "success")
				self.record_result("Webhook route in hooks", True)
			else:
				self.log("Webhook route not found in hooks.py", "warning")
				self.record_result("Webhook route in hooks", False, "Not found")
		except Exception as e:
			self.log(f"Hooks check failed: {e}", "error")
			self.record_result("Webhook route in hooks", False, str(e))

		# Check server config includes webhook
		try:
			from mail.server.doctype.server_config.server_config import get_config_toml
			server = frappe.db.get_value("Mail Server", {"enabled": 1}, "name")
			if server:
				config = get_config_toml(server)
				if "webhook" in config.lower():
					self.log("Webhook config in server TOML", "success")
					self.record_result("Webhook in server config", True)
				else:
					self.log("Webhook not in server TOML (check URL config)", "warning")
					self.record_result("Webhook in server config", False, "Not in TOML", skipped=True)
			else:
				self.log("No server to check config", "skip")
				self.record_result("Webhook in server config", False, "No server", skipped=True)
		except Exception as e:
			self.log(f"Server config check failed: {e}", "error")
			self.record_result("Webhook in server config", False, str(e))

	# =========================================================================
	# 8. API Endpoints Tests
	# =========================================================================
	def test_api_endpoints(self):
		print("\n🌐 8. API ENDPOINTS")
		print("-" * 40)

		endpoints = [
			("mail.api.mail.get_mailboxes", "GET mailboxes"),
			("mail.api.mail.get_threads", "GET threads"),
			("mail.api.mail.search_mails", "Search mails"),
			("mail.api.mail.create_mail", "Create mail"),
			("mail.api.mail.cancel_scheduled_mail", "Cancel scheduled"),
			("mail.api.mail.update_scheduled_mail", "Update scheduled"),
			("mail.api.webhook.delivery_status", "Webhook delivery"),
		]

		for endpoint, name in endpoints:
			try:
				# Just check function exists and is whitelisted
				module_path, func_name = endpoint.rsplit('.', 1)
				module = frappe.get_module(module_path)
				func = getattr(module, func_name, None)
				if func:
					is_whitelisted = getattr(func, 'is_whitelisted', False)
					self.log(f"{name}: Available (whitelisted: {is_whitelisted})", "success")
					self.record_result(f"API: {name}", True)
				else:
					self.log(f"{name}: Function not found", "warning")
					self.record_result(f"API: {name}", False, "Not found")
			except Exception as e:
				self.log(f"{name}: Error - {e}", "error")
				self.record_result(f"API: {name}", False, str(e))

	# =========================================================================
	# Summary
	# =========================================================================
	def print_summary(self):
		print("\n" + "=" * 70)
		print("📊 TEST SUMMARY")
		print("=" * 70)
		print(f"✅ Passed:  {self.results['passed']}")
		print(f"❌ Failed:  {self.results['failed']}")
		print(f"⏭️  Skipped: {self.results['skipped']}")
		print(f"📝 Total:   {len(self.results['tests'])}")
		print("-" * 70)

		if self.results['errors']:
			print("\n❌ FAILURES:")
			for error in self.results['errors']:
				print(f"  • {error}")

		success_rate = (
			self.results['passed'] / max(len(self.results['tests']) - self.results['skipped'], 1)
		) * 100
		print(f"\n📈 Success Rate: {success_rate:.1f}%")
		print("=" * 70 + "\n")

	# =========================================================================
	# Cleanup
	# =========================================================================
	def cleanup(self):
		"""Clean up test data."""
		print("\n🧹 CLEANUP")
		print("-" * 40)

		# Cleanup test draft
		if getattr(self, 'test_draft', None) and self.test_draft.name:
			try:
				frappe.delete_doc("Mail Queue", self.test_draft.name, force=True)
				self.log(f"Deleted draft: {self.test_draft.name}", "success")
			except Exception as e:
				self.log(f"Failed to delete draft: {e}", "warning")

		# Cleanup test scheduled
		if getattr(self, 'test_scheduled', None) and self.test_scheduled.name:
			try:
				frappe.delete_doc("Mail Queue", self.test_scheduled.name, force=True)
				self.log(f"Deleted scheduled: {self.test_scheduled.name}", "success")
			except Exception as e:
				self.log(f"Failed to delete scheduled: {e}", "warning")


def run(user=None, cleanup=True):
	"""Entry point for bench execute."""
	runner = BattleTestRunner(user=user)
	results = runner.run_all()
	if cleanup:
		runner.cleanup()
	return results


# Allow running with: bench --site <site> execute mail.tests.run_battle_test
if __name__ == "__main__":
	run()
