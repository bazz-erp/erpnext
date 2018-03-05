# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
    return get_columns(), get_data(filters)


def get_columns():
    return [
        _("Operation") + ":Data:140",
        _("Date") + ":Date:120",
        _("Item Code") + ":Link/Item:80",
        _("Item Name") + ":Data:140",
        _("Qty") + ":Float:80",
        _("Debit") + ":Currency:80",
        _("Credit") + ":Currency:80",
        _("Balance") + ":Currency:80"
    ]

def get_data(filters):
    data = []
    if not (filters.get("workshop") and filters.get("company")):
        frappe.throw(_("{0} and {1} are mandatory".format(_("Workshop"), _("Company"))))

    entries = frappe.db.sql("""SELECT item.item_name, sd.item_code, sd.qty, sd.amount, sd.s_warehouse, 
    sd.t_warehouse, se.posting_date, se.purpose FROM `tabStock Entry` as se, 
`tabStock Entry Detail` as sd, `tabItem` as item, `tabProduction Order` as po, 
`tabOperation Completion` as op where op.workshop = %(workshop)s and sd.parent = se.name
and se.operation = op.name and sd.item_code = item.name and op.production_order=po.name 
and po.company=%(company)s and t_warehouse is not null 
order by se.posting_date""", filters, as_dict=1)

    balance = 0
    for entry in entries:
        entry["debit"] = entry.get("amount") if entry.get("purpose") == "Manufacturer Shipping" else 0
        entry["credit"] = entry.get("amount") if entry.get("purpose") == "Manufacturer Receipt" else 0
        balance += entry["debit"] - entry["credit"]
        data.append([_(entry.get("purpose")), entry.get("posting_date"), entry.get("item_code"),
                     entry.get("item_name"), entry.get("qty"), entry.get("debit"), entry.get("credit"), balance])

    return data
