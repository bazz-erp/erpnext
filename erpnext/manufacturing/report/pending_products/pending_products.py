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
    columns = [_("Item Code") + ":Link/Item:80",
               _("Item Name") + ":Data:140",
               _("Workshop") + ":Link/Supplier:150",
               _("Operation") + ":Link/Operation Completion:150",
               _("Production Order") + ":Link/Production Order:140",
               _("Pending Qty") + ":Float:140",
               _("Unit of Measure") + ":Link/UOM:120",
               _("Customer") + ":Link/Customer:120",
               _("Sales Order") + ":Link/Sales Order:120"]
    return columns


def get_data(filters):
    data = []

    group_field = get_group_field(filters)

    query = """select op.completion, op.parent as production_order, op.workshop,
    po.production_item, item.item_name, item.stock_uom, so.name as so_name, so.customer_name, so.customer 
    from `tabProduction Order Operation` as op, `tabProduction Order` po {join_type} 
    `tabSales Order` as so on po.sales_order = so.name, `tabItem` as item where {conditions} order by {order_by}"""

    """If report is grouping by client, only production orders that has a target client must be showed, thus
    the query makes an inner join. Else, if the group field is product or workshop, all pending operations must be
    showed"""
    join_type = "inner join" if filters.get("group_by") == "Customer" else "left join"

    query = query.format(conditions=get_conditions(filters), order_by=get_order_by(filters), join_type=join_type)

    in_process_operations = frappe.db.sql(query,filters,as_dict=1)

    return get_data_grouped_by_field(in_process_operations, group_field)

def get_conditions(filters):
    conditions = ["""op.parent = po.name and po.production_item = item.item_code and op.status = 'In Process'"""]
    if filters.get("workshop"):
        conditions.append("op.workshop=%(workshop)s")
    if filters.get("item"):
        conditions.append("item.item_code = %(item)s")
    if filters.get("customer"):
        conditions.append("so.customer=%(customer)s")
    return "{}".format(" and ".join(conditions)) if conditions else ""

def get_order_by(filters):
    if filters.get("group_by") == "Workshop":
        return """op.workshop, po.production_item"""
    if filters.get("group_by") == "Item":
        return """po.production_item, op.workshop"""
    # group by client
    else:
        return """so.customer desc,op.workshop, po.production_item"""

def get_data_grouped_by_field(in_process_operations, group_field):
    data = []
    current_value = None
    sub_group_field = "workshop" if group_field == "production_item" else "production_item"
    sub_group_current_value = None
    total_item_qty = 0

    for operation in in_process_operations:
        item_remaining_qty = calculate_production_item_remaining_qty(operation.completion)

        if current_value != operation.get(group_field) and item_remaining_qty != 0:

            current_value = operation.get(group_field)
            total_item_qty, sub_group_current_value = reset_sub_group_total(data,sub_group_field,operation,total_item_qty)
            add_title_row(data, group_field, operation)

        elif sub_group_current_value != operation.get(sub_group_field):
            total_item_qty, sub_group_current_value = reset_sub_group_total(data, sub_group_field, operation,
                                                                            total_item_qty)
        if item_remaining_qty != 0:
            add_data_row(data, group_field, operation, item_remaining_qty)
            total_item_qty += item_remaining_qty

    # add last Total line
    if total_item_qty != 0:
        add_total_item_qty_row(data, total_item_qty)
    return data

def reset_sub_group_total(data,sub_group_field, operation, total_item_qty):
    if total_item_qty != 0:
        add_total_item_qty_row(data, total_item_qty)
    return 0, operation.get(sub_group_field)


def add_title_row(data, group_field, operation):
    data.append([])
    if group_field == "workshop":
        data.append([None, None, operation.get("workshop")])
    elif group_field == "production_item":
        data.append([operation.get("production_item"), operation.get("item_name")])
    else:
        data.append([None, operation.get("customer_name"), None, None, None, None, None])

def add_data_row(data, group_field, operation, item_remaining_qty):
    row = [operation.get("production_item"), operation.get("item_name"),
           operation.get("workshop"),operation["completion"], operation["production_order"],
           item_remaining_qty, operation["stock_uom"], operation.get("customer_name"), operation.get("so_name")]

    if group_field == "production_item":
        row[0] = None
        row[1] = None
    elif group_field == "workshop":
        row[2] = None
    else:
        row[7] = None
    data.append(row)

def add_total_item_qty_row(data,total_item_qty):
    data.append([None, None,None, None, None,total_item_qty])
    data.append([])

def get_group_field(filters):
    group_fields = {"Workshop": "workshop", "Item": "production_item", "Customer": "customer"}
    if not filters.get("group_by"):
        frappe.throw(_("Group by field is mandatory"))
    return group_fields.get(filters.get("group_by"))





