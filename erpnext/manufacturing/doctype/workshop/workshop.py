# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
import erpnext

class Workshop(Document):

    def validate(self):
        self.validate_code()
        self.create_workshop_warehouse()


    def validate_code(self):
        if self.is_new():
            existing_code = frappe.db.sql("""select workshop_code from tabWorkshop where workshop_code = %s""", self.workshop_code)
            if existing_code:
                frappe.throw(_("Workshop code already exists"))

    def create_workshop_warehouse(self):
        if not self.workshop_warehouse:
            warehouse = frappe.get_doc({"doctype": "Warehouse", "is_group": 0, "company": erpnext.get_default_company(),
                                        "warehouse_name": self.workshop_name})
            warehouse.save()
            self.workshop_warehouse = warehouse.name

