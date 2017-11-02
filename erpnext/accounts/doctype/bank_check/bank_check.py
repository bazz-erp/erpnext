# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class BankCheck(Document):
	pass


@frappe.whitelist()
def get_last_internal_number():
	return frappe.db.sql("""SELECT COALESCE(MAX(internal_number), 0) FROM `tabBank Check` """)