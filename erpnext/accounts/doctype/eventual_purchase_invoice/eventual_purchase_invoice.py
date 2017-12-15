# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnext.accounts.general_ledger import make_gl_entries
from frappe.utils import nowdate

class EventualPurchaseInvoice(Document):

    def autoname(self):
        self.name = self.supplier_name + " - " + self.invoice_number


    def validate(self):
        self.set_status()


    def set_status(self, update = True):
        if self.is_new():
            self.status = 'Draft'

        elif self.docstatus == 1 and self.outstanding_amount > 0:
            self.status = 'Unpaid'

        elif self.docstatus == 1 and self.outstanding_amount <= 0:
            self.status = 'Paid'

        if update:
            self.db_set("status", self.status)


    def on_submit(self):
        self.make_gl_entries()

    def make_gl_entries(self):
        gl_entries = []
        self.make_supplier_gl_entry(gl_entries)
        make_gl_entries(gl_entries)

    def make_supplier_gl_entry(self, gl_entries):
        default_payable_account = frappe.get_doc("Company", self.company).default_payable_account
        stock_received_but_not_billed = frappe.get_doc("Company", self.company).stock_received_but_not_billed
        gl_entries.append(
            frappe._dict({
                'company': self.company,
                'posting_date': nowdate(),
                "account": default_payable_account,
                "party_type": "Supplier",
                "credit": self.total_amount,
                "credit_in_account_currency": self.total_amount,
                "voucher_no": self.name,
                "voucher_type": self.doctype,
                "against": self.supplier_name
            })
        )

        gl_entries.append(
            frappe._dict({
                "party_type": "Supplier",
                "account": stock_received_but_not_billed,
                "debit": self.total_amount,
                "debit_in_account_currency": self.total_amount,
                "voucher_no": self.name,
                "voucher_type": self.doctype,
                "against": default_payable_account
            })
        )







