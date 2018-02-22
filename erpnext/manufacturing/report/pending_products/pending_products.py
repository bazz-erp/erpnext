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
               _("Unit of Measure") + ":Link/UOM:120",
               _("Customer") + ":Link/Customer:120"]
    return columns


def get_data(filters):
    data = []

    group_field = get_group_field(filters)

    query = """select {projection} from {source} where {conditions} order by {order_by}"""

    query = query.format(projection=get_projection(filters),source=get_source(filters),conditions=get_conditions(filters), order_by=get_order_by(filters))

    in_process_operations = frappe.db.sql(query,filters,as_dict=1)



    return get_data_grouped_by_field(in_process_operations, group_field)

def get_source(filters):
    source = """`tabProduction Order Operation` as op, `tabProduction Order` po, `tabItem` as item"""
    if filters.get("group_by") == "Customer" or filters.get("customer"):
        source += """, `tabSales Order` as so"""
    return source

def get_projection(filters):
    projection = """op.completion, op.parent as production_order, 
    op.workshop, po.production_item as production_item, item.item_name as item_name, item.stock_uom"""

    if filters.get("group_by") == "Customer" or filters.get("customer"):
        projection += ", so.customer, so.customer_name"
    return projection

def get_conditions(filters):
    conditions = ["""op.parent = po.name and po.production_item = item.item_code and op.status = 'In Process'"""]

    if filters.get("group_by") == "Customer" or filters.get("customer"):
        conditions.append("po.sales_order = so.name")

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
        return """so.customer,op.workshop, po.production_item"""

def get_data_grouped_by_field(in_process_operations, group_field):
    data = []
    current_value = None
    for operation in in_process_operations:
        item_remaining_qty = calculate_production_item_remaining_qty(operation.completion)
        if current_value != operation.get(group_field) and item_remaining_qty != 0:
            current_value = operation.get(group_field)
            add_title_row(data, group_field, operation)
        if item_remaining_qty != 0:
            add_data_row(data, group_field, operation, item_remaining_qty)
    return data

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
           item_remaining_qty, operation["stock_uom"], operation.get("customer_name", None)]

    if group_field == "production_item":
        row[0] = None
        row[1] = None
    elif group_field == "workshop":
        row[2] = None
    else:
        row[7] = None
    data.append(row)

def get_group_field(filters):
    group_fields = {"Workshop": "workshop", "Item": "production_item", "Customer": "customer"}
    if not filters.get("group_by"):
        frappe.throw(_("Group by field is mandatory"))
    return group_fields.get(filters.get("group_by"))





