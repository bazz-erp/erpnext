# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnext.accounts.general_ledger import make_gl_entries
from frappe.utils import nowdate, flt
from frappe import _

class EventualPurchaseInvoice(Document):

    def validate(self):
        self.validate_dates()
        self.check_mandatory()
        self.validate_cuit()
        self.set_total_amount()
        self.set_status()

        # Removes 'Draft' transition, submit document directly
        self._action = "submit"
        self.docstatus = 1

    def validate_dates(self):
        if not self.issue_date:
            self.issue_date = nowdate()

        if not self.iva_date:
            self.iva_date = nowdate()

    def validate_cuit(self):
        if not self.cuit.isdigit():
            frappe.throw(_("{0} field must contain only digits"))
        if len(self.cuit) > 11:
            frappe.throw (_("CUIT has 11 numbers as maximum"))

    def set_status(self, update = False):
        if self.is_new():
            self.status = 'Draft'

        elif self.docstatus == 1 and self.outstanding_amount > 0:
            self.status = 'Unpaid'

        elif self.docstatus == 1 and self.outstanding_amount <= 0:
            self.status = 'Paid'

        if update:
            self.db_set("status", self.status)


    def check_mandatory(self):
        for field in ["supplier_name", "cuit", "iva_type", "taxed_amount_21", "taxed_amount_10",
                      "taxed_amount_27", "iva_21", "iva_10", "iva_27"]:
            if self.get(field) == None:
                frappe.throw(_("{0} in Eventual Purchase Invoice is mandatory").format(self.meta.get_label(field)))

    def set_total_amount(self):
        total_amount = 0
        for field in ["taxed_amount_21", "taxed_amount_10",
                      "taxed_amount_27", "iva_21", "iva_10", "iva_27", "exempts", "others", "iva_perception", "ibb_perception"]:

            if self.get(field):
                total_amount += flt(self.get(field))

        self.total_amount = total_amount




    def on_submit(self):
        self.make_gl_entries()
        self.set_status(update = True)

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
                "against_voucher": self.name,
                "against_voucher_type": self.doctype,
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







