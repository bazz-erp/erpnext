# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class Freight(Document):
	pass


@frappe.whitelist()
def get_address(name):
	return frappe.db.sql("""SELECT * FROM `tabFreight` WHERE freight_name=%s """, name, as_dict=1)[0]
