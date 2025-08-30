# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

# import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class UnitTestMailAccount(UnitTestCase):
	"""
	Unit tests for MailAccount.
	Use this class for testing individual functions and methods.
	"""

	def test_generate_app_password(self):
		"""Test that app password is generated when password is set."""
		from mail.mail.doctype.mail_account.mail_account import MailAccount
		
		# Create a mock MailAccount document
		doc = MailAccount()
		doc._generate_app_password()
		
		# Check that app password was generated
		self.assertTrue(hasattr(doc, 'app_password'))
		self.assertIsNotNone(doc.app_password)
		self.assertEqual(len(doc.app_password), 32)

	def test_app_password_regeneration(self):
		"""Test that app password can be regenerated."""
		from mail.mail.doctype.mail_account.mail_account import MailAccount
		
		doc = MailAccount()
		doc._generate_app_password()
		first_password = doc.app_password
		
		doc._generate_app_password()
		second_password = doc.app_password
		
		# Check that passwords are different
		self.assertNotEqual(first_password, second_password)


class IntegrationTestMailAccount(IntegrationTestCase):
	"""
	Integration tests for MailAccount.
	Use this class for testing interactions between multiple components.
	"""

	pass
