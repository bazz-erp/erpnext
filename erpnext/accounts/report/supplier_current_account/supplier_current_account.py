# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe import _
import frappe

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    columns = [
        _("Date") + ":Date:90",  _("Voucher Type") + "::120",
        _("Voucher No") + ":Dynamic Link/"+ _("Voucher Type")+":160",
        _("Debit") + ":Currency:100", _("Credit") + ":Currency:100", _("Balance") + ":Currency:100"
    ]
    return columns

def get_data(filters):
    data = []
    if not filters.get("supplier"):
        frappe.throw(_("Supplier name is mandatory"))

    gl_entries = frappe.db.sql("""select posting_date, voucher_type, voucher_no, debit, credit from `tabGL Entry` where party_type = 'Supplier' and party=%(supplier)s""", filters, as_dict = 1)

    balance = 0
    total_credit = 0
    total_debit = 0
    for entrie in gl_entries:
        balance += entrie.debit - entrie.credit
        total_credit += entrie.credit
        total_debit += entrie.debit
        data.append([entrie.posting_date, entrie.voucher_type, entrie.voucher_no, entrie.debit, entrie.credit, balance])
    data.append([])
    data.append([None, _("Total"), None, None, None, balance ])
    return data