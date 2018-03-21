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
        _("UOM") + ":Link/UOM:80",
        _("Debit") + ":Currency:80",
        _("Credit") + ":Currency:80",
        _("Balance") + ":Currency:80"
    ]

def get_data(filters):
    data = []
    if not (filters.get("workshop") and filters.get("company")):
        frappe.throw(_("{0} and {1} are mandatory".format(_("Workshop"), _("Company"))))

    payment_entries = get_workshop_payment_entries(filters)

    stock_entry_details = get_stock_entry_details(filters)

    entries = payment_entries + stock_entry_details
    balance = 0
    for entry in sorted(entries, key=lambda e: e["creation"]):
        entry["debit"] = entry.get("amount") if (entry.get("purpose") == "Manufacturer Shipping"
                                                 or entry.get("purpose") == "Payment") else 0

        entry["credit"] = entry.get("amount") if entry.get("purpose") == "Manufacturer Receipt" else 0

        balance += entry["debit"] - entry["credit"]
        data.append([_(entry.get("purpose")), entry.get("posting_date"), entry.get("item_code"),
                     entry.get("item_name"), entry.get("qty"), entry.get("uom"), entry.get("debit"), entry.get("credit"), balance])

    data.append([])
    data.append([_("Total"),None, None,None,None,None,None, None, balance])
    return data

def get_stock_entry_details(filters):
    return frappe.db.sql("""SELECT sd.creation, item.item_name, sd.item_code, sd.qty, sd.amount, sd.s_warehouse, 
            sd.t_warehouse, sd.uom, se.posting_date, se.purpose FROM `tabStock Entry` as se, 
        `tabStock Entry Detail` as sd, `tabItem` as item, `tabProduction Order` as po, 
        `tabOperation Completion` as op
        where op.workshop = %(workshop)s and sd.parent = se.name
        and se.operation = op.name and sd.item_code = item.name and op.production_order=po.name 
        and po.company=%(company)s and (se.purpose = 'Manufacturer Shipping' or se.purpose = 'Manufacturer Receipt') 
        order by se.posting_date, sd.creation""", filters, as_dict=1)




def get_workshop_payment_entries(filters):
    return frappe.db.sql("""select creation, posting_date, paid_amount as amount, 'Payment' as purpose from `tabPayment Entry` 
where party_type='Supplier' and party=%(workshop)s order by posting_date, creation""", filters, as_dict=1)

