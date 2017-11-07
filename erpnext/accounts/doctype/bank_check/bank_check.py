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


@frappe.whitelist()
def get_unused_third_party_checks(company):
    return frappe.db.sql("""SELECT payment_date, bank, internal_number, amount, number FROM
    `tabBank Check` WHERE company=%(company)s and third_party_check and used=FALSE """, {"company": company}, as_dict=1)