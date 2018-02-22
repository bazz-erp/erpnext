# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from erpnext.manufacturing.doctype.operation_completion.operation_completion import calculate_production_item_remaining_qty

def execute(filters=None):
    columns = get_columns()
    return columns, get_data(filters)


def get_columns():
    columns = [_("Item Code") + ":Link/Item:140",
               _("Item Name") + ":Data:140",
               _("Workshop") + ":Link/Supplier:100",
               _("Operation") + ":Link/Operation Completion:150",
               _("Production Order") + ":Link/Production Order:140",
               _("Pending Qty") + ":Float:140",
               _("Unit of Measure") + ":Link/UOM:120"]
    return columns


def get_data(filters):
    data = []

    query = """select op.completion, op.parent as production_order, 
    op.workshop, po.production_item as production_item, item.item_name as item_name, item.stock_uom 
    from `tabProduction Order Operation` as op, `tabProduction Order` po, `tabItem` as item where 
    op.parent = po.name and po.production_item = item.item_code and op.status = 'In Process'"""

    if any(filters):
        query+=""" and {conditions}"""
        query = query.format(conditions=get_conditions(filters))

    query+= """ order by op.workshop, po.production_item"""

    in_process_operations = frappe.db.sql(query,filters,as_dict=1)

    for operation in in_process_operations:
        item_qty = calculate_production_item_remaining_qty(operation.completion)

        if item_qty != 0:
            data.append([operation["production_item"], operation["item_name"], operation["workshop"],
                     operation["completion"], operation["production_order"], item_qty, operation["stock_uom"]])

    return data

def get_conditions(filters):
    conditions = []
    if filters.get("workshop"):
        conditions.append("op.workshop=%(workshop)s")
    if filters.get("item"):
        conditions.append("item.item_code = %(item)s")
    return "{}".format(" and ".join(conditions)) if conditions else ""



