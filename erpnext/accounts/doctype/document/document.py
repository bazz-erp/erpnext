# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document as FrappeDocument

class Document(FrappeDocument):
	pass


@frappe.whitelist()
def get_last_internal_number():
	return frappe.db.sql("""SELECT COALESCE(MAX(CAST(internal_number AS INTEGER)), 0) FROM `tabDocument` """)

@frappe.whitelist()
def get_unused_third_party_documents(company):
    return frappe.db.sql("""SELECT name, date, internal_number, amount, client_detail FROM
    `tabDocument` WHERE company=%(company)s and third_party and used=FALSE """, {"company": company}, as_dict=1)