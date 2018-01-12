# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry_for_eventual_purchase_invoice

class TestEventualPurchaseInvoice(unittest.TestCase):

    def make_eventual_purchase_invoice(self):
        e_invoice = frappe.new_doc("Eventual Purchase Invoice")
        e_invoice.company = frappe.db.get_single_value('Global Defaults', 'default_company')
        e_invoice.supplier_name = "Test Supplier"
        e_invoice.iva_type = "Inscripto"
        e_invoice.cuit = "1245"

        e_invoice.taxed_amount_21 = 1000
        e_invoice.iva_21 = e_invoice.taxed_amount_21 * 0.21

        e_invoice.taxed_amount_10 = 200
        e_invoice.iva_10 = e_invoice.taxed_amount_10 * 0.105

        e_invoice.taxed_amount_27 = 300
        e_invoice.iva_27 = e_invoice.taxed_amount_27 * 0.27

        return e_invoice

    def test_eventual_purchase_invoice(self):
        e_invoice = self.make_eventual_purchase_invoice()
        e_invoice.save()

        # reload document to refresh outstanding amount
        e_invoice = frappe.get_doc("Eventual Purchase Invoice", e_invoice.name)

        self.assertEquals(e_invoice.total_amount, 1812)
        self.assertEquals(e_invoice.total_amount, e_invoice.outstanding_amount)
        self.assertEquals(e_invoice.status, 'Unpaid')

        # test Eventual Purchase Invoice Payment
        payment_entry = get_payment_entry_for_eventual_purchase_invoice(e_invoice.name)

        cash_mode_of_payment = frappe.get_value("Mode of Payment",{"type": "Cash"}, "name")

        company = frappe.get_doc("Company", frappe.db.get_single_value('Global Defaults', 'default_company'))

        cash_account = frappe.db.sql("""select default_account from `tabMode of Payment Account` 
where company=%(company)s and parent=%(mode_of_payment)s""", {"company": company.name, "mode_of_payment": cash_mode_of_payment})[0][0]

        payment_entry.append("lines", {"mode_of_payment": cash_mode_of_payment, "paid_amount": e_invoice.outstanding_amount,
                                       "paid_from": cash_account, "paid_to": company.default_payable_account})

        payment_entry.save()

        # reload document to refresh outstanding amount
        e_invoice = frappe.get_doc("Eventual Purchase Invoice", e_invoice.name)

        self.assertEquals(e_invoice.outstanding_amount, 0)









