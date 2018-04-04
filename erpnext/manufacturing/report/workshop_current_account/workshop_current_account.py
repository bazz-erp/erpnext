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

    payment_entries = get_workshop_gl_entries(filters)

    stock_entry_details = get_stock_entry_details(filters)

    entries = payment_entries + stock_entry_details
    balance = 0
    for entry in sorted(entries, key=lambda e: e["posting_date"] and e["creation"]):

        balance += entry.get("debit", 0) - entry.get("credit", 0)

        # the function _ is explicitly invoked with the term 'Workforce' to translate it
        entry["purpose"] = _("Workforce") if entry.get("purpose") == "Workforce" else entry["purpose"]

        data.append([_(entry.get("purpose")), entry.get("posting_date"), entry.get("item_code"),
                     entry.get("item_name"), entry.get("qty"), entry.get("uom"), entry.get("debit"), entry.get("credit"), balance])

    data.append([])
    data.append([_("Total"),None, None,None,None,None,None, None, balance])
    return data

def get_stock_entry_details(filters):
    item_filter = " and sd.item_code=%(item)s " if filters.get("item") else ""

    return frappe.db.sql("""SELECT sd.creation, item.item_name, sd.item_code, sd.qty, sd.amount, sd.s_warehouse, 
            sd.t_warehouse, sd.uom, se.posting_date, se.purpose FROM `tabStock Entry` as se, 
        `tabStock Entry Detail` as sd, `tabItem` as item, `tabProduction Order` as po, 
        `tabOperation Completion` as op
        where op.workshop = %(workshop)s and sd.parent = se.name
        and se.operation = op.name and sd.item_code = item.name and op.production_order=po.name 
        and po.company=%(company)s and (se.purpose = 'Manufacturer Shipping' or se.purpose = 'Manufacturer Receipt')
        {group_list}
        {item_filter} 
        order by se.posting_date, sd.creation""".format(item_filter=item_filter, group_list=get_selected_item_groups()),filters, as_dict=1)



def get_workshop_gl_entries(filters):
    return frappe.db.sql("""select creation, posting_date, credit, debit, if(voucher_type = "Payment Entry", "Payment", "Workforce") as purpose from `tabGL Entry` 
    where company=%(company)s and party_type='Supplier' and party=%(workshop)s and against_voucher_type='Operation Completion'
    order by posting_date, creation""", filters, as_dict=1)


def get_selected_item_groups():
    checked_item_groups = frappe.db.sql("""select item_group from `tabChecked Item Group` where parentfield='item_groups_table' 
and parenttype='Manufacturing Settings'""")

    selected_item_groups = []
    for item_group in checked_item_groups:
        selected_item_groups.append(item_group[0])
        get_item_group_subgroups(item_group, selected_item_groups)

    # return group list in the form ('A', 'B', 'C') to add to the query, null represents empty item group set
    selected_item_groups = ["'" + item_group + "'" for item_group in selected_item_groups]
    return "and item.item_group in (" + ",".join(selected_item_groups) + ")" if selected_item_groups else "and item.item_group is null"

def get_item_group_subgroups(item_group, item_group_list):
    """ finds all subgroups of an item group recursively and adds it to item_group_list"""
    subgroups = frappe.db.sql("""select name from `tabItem Group` where parent_item_group=%s""", item_group)

    # convert from list of tuples to list of strings
    subgroups_list = [item_group[0] for item_group in subgroups]
    item_group_list += subgroups_list
    for item_subgroup in subgroups_list:
        get_item_group_subgroups(item_subgroup, item_group_list)




