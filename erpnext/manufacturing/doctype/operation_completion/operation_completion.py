# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from erpnext.manufacturing.doctype.bom.bom import get_bom_items_as_dict
import json

class ProductionOrderNotStartedError(frappe.ValidationError): pass

class OperationCompletion(Document):

    def autoname(self):
        self.name = self.production_order + " - " + self.operation

    def validate(self):
        for field in ["operation", "production_order"]:
            if not self.get(field):
                frappe.throw(_("{0} is mandatory in Operation Completion").format(self.meta.get_label(field)))


    def start_operation(self, workshop, items_supplied):

        if self.status == 'Completed':
           frappe.throw(_("Operation is already completed."))

        production_order = frappe.get_doc("Production Order", self.production_order)

        if production_order.status != 'In Process':
            frappe.throw(_("Production Order must be In Process to start an operation"), ProductionOrderNotStartedError)

        if self.status == "Pending" and not workshop:
            frappe.throw(_("Workshop is mandatory when sending materials for the first time"))

        po_operation = filter(lambda op: op.completion == self.name, production_order.operations)[0]

        # supplied qty of production item cannot be greather than qty received in previous operation
        production_item_available_qty = get_production_item_available_qty(production_order, po_operation)
        if items_supplied.get(production_order.production_item) and items_supplied.get(production_order.production_item) > production_item_available_qty:
            frappe.throw(_("Available qty of production item is {0}").format(production_item_available_qty))

        if self.status == 'Pending':
            self.db_set("status", "In Process")
            self.db_set("workshop", workshop)
            self.db_set("start_date", frappe.utils.nowdate())

            po_operation.db_set("status", "In Process")
            po_operation.db_set("workshop", workshop)
            production_order.update_status()

        # Clear items whose transferred qty is 0 and update total qty supplied to the workshop in items supplied Table
        for item_code, item_qty in items_supplied.items():
            if item_qty == 0:
                items_supplied.pop(item_code)

            items_supplied_detail = self.get("items_supplied", {"item_code": item_code})
            if not items_supplied_detail:
                self.append("items_supplied", {"item_code": item_code, "item_qty": item_qty})
                self.save()
            else:
                items_supplied_detail[0].item_qty += item_qty
                items_supplied_detail[0].save()


        self.transfer_material_to_workshop(production_order, items_supplied)

    def finish_operation(self, operating_cost, items_received):
        if not self.status == 'In Process':
            frappe.throw(_("Operation must be started to send materials."))

        if operating_cost is None:
            frappe.throw(_("Operation cost is mandatory"))

        production_order = frappe.get_doc("Production Order", self.production_order)
        production_item_received_qty = flt(items_received.get(production_order.production_item, 0))

        if production_item_received_qty <= 0:
            frappe.throw(_("Quantity must be greater than 0."))

        po_operation = filter(lambda op: op.completion == self.name, production_order.operations)[0]
        remaining_production_item_qty = calculate_production_item_remaining_qty(self.name)

        # in the first operation production item is not sent, thus, remaining qty is always 0.
        # validation of remaining qty must be done in subsequents operations
        if po_operation.idx > 1 and production_item_received_qty > remaining_production_item_qty:
            frappe.throw(_("Remaining qty of production item is {0}").format(remaining_production_item_qty))


        filtered_items = {code: qty for code, qty in items_received.items() if qty != 0}

        for item_code, item_qty in filtered_items.items():
            items_received_detail = self.get("items_received", {"item_code": item_code})
            if not items_received_detail:
                self.append("items_received", {"item_code": item_code, "item_qty": item_qty})
                self.save()
            else:
                items_received_detail[0].item_qty += item_qty
                items_received_detail[0].save()


        self.receive_material_from_workshop(production_order, filtered_items)

        self.db_set("total_operating_cost", self.total_operating_cost + operating_cost)
        self.db_set("total_received_qty", self.total_received_qty + production_item_received_qty)

        production_order.db_set("operations_cost", production_order.operations_cost + operating_cost)
        production_order.db_set("total_cost", production_order.total_cost + operating_cost)

        if (self.total_received_qty == production_order.qty):
            self.db_set("status", "Completed")
            po_operation.db_set("status", "Completed")
            production_order.update_status()

    def transfer_material_to_workshop(self, production_order, items_supplied):
        stock_entry = self.create_stock_entry(production_order)

        stock_entry.purpose = "Manufacturer Shipping"
        stock_entry.title = _("Material Transfer to Workshop")
        workshop_warehouse = self.get_workshop_warehouse(production_order.company)

        stock_entry.from_warehouse = production_order.wip_warehouse
        stock_entry.to_warehouse = workshop_warehouse

        for item_code, item_qty in items_supplied.items():
            stock_entry.append("items", {"item_code": item_code, "qty": item_qty})

        stock_entry.submit()


    def receive_material_from_workshop(self, production_order, items_received):
        stock_entry = self.create_stock_entry(production_order)
        stock_entry.purpose = "Manufacturer Receipt"

        stock_entry.title = _("Receive Material from Workshop")

        """production item must be transferred to 'work in progress' warehouse. 
        If this item was sent, it must be deducted from the workshop's warehouse. 
        Else, if the workshop origin the product, source warehouse is null"""
        for item_code, item_qty in items_received.items():
            product_dict = {"item_code": item_code, "qty": item_qty, "t_warehouse": production_order.wip_warehouse}
            if item_code == production_order.production_item:
                product_dict["s_warehouse"] = self.get_workshop_warehouse(production_order.company) if self.is_production_item_supplied(production_order.production_item) else None
            else:
                product_dict["s_warehouse"] = self.get_workshop_warehouse(production_order.company)
            stock_entry.append("items", product_dict)

        self.consume_raw_materials(stock_entry, production_order, items_received)
        stock_entry.submit()

    def get_workshop_warehouse(self, company):
        return frappe.get_doc("Supplier", self.workshop).get_company_warehouse(company)


    def is_production_item_supplied(self, production_item):
        production_item_supplied = self.get("items_supplied", {"item_code": production_item})
        return production_item_supplied and production_item_supplied[0].item_qty != 0


    def consume_raw_materials(self,stock_entry,production_order, items_received):
        if self.is_production_item_supplied(production_order.production_item):
            return
        production_item_received_qty = items_received.get(production_order.production_item)

        """based on production_item_qty raw materials in the workshop's warehouse are deducted"""
        bom_items = get_bom_items_as_dict(production_order.bom_no, production_order.company, qty=production_item_received_qty,
                                          fetch_exploded=production_order.use_multi_level_bom)
        for bom_item in bom_items.values():
            print (str(bom_item["item_code"]) + " - " +  str(bom_item["qty"]))
            stock_entry.append("items", {"item_code": bom_item["item_code"], "qty": bom_item["qty"],
                                         "s_warehouse": self.get_workshop_warehouse(production_order.company)})

    def create_stock_entry(self, production_order):
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.production_order = production_order.name
        stock_entry.company = production_order.company
        stock_entry.from_bom = 0
        stock_entry.operation = self.name
        return stock_entry


@frappe.whitelist()
def get_available_materials(operation_id, previous_operation_id):
    """ get the available products that can be send to a Workshop in an Operation Completion.
    This result is calculated depending on the qty received in previous operation and the qty already sent in current operation"""

    operation = frappe.get_doc("Operation Completion", operation_id)
    previous_operation = frappe.get_doc("Operation Completion", previous_operation_id)

    received_materials = []
    """ for each item calculates its available qty based on the qty received in previous operation and the qty already sent in current operation"""
    for item in previous_operation.items_received:
        item_sent = operation.get("items_supplied", {"item_code": item.item_code})

        item_available_qty = (item.item_qty - item_sent[0].item_qty) if item_sent else item.item_qty

        received_materials.append({"item_code": item.item_code, "item_qty": item_available_qty})
    return received_materials


"""When the production item (final product) is sent to the Workshop, calculates remaining qty that must be received from the workshop"""
@frappe.whitelist()
def calculate_production_item_remaining_qty(operation_id):
    operation = frappe.get_doc("Operation Completion", operation_id)
    production_order = frappe.get_doc("Production Order", operation.production_order)

    production_item_supplied = operation.get("items_supplied", {"item_code": production_order.production_item})

    # check if production item was send to the workshop
    if operation.is_production_item_supplied(production_order.production_item):
        production_item_received = operation.get("items_received", {"item_code": production_order.production_item})
        return (production_item_supplied[0].item_qty - production_item_received[0].item_qty) if production_item_received else production_item_supplied[0].item_qty
    return 0


def get_production_item_available_qty(production_order, production_order_operation):
    # operation has no predecessor
    if production_order_operation.idx == 1:
        return 0

    previous_operation_id = filter(lambda op: (op.idx + 1) == production_order_operation.idx, production_order.operations)[0].completion
    available_materials = get_available_materials(production_order_operation.completion, previous_operation_id)
    production_item = filter(lambda item: item["item_code"] == production_order.production_item, available_materials)
    return production_item[0]["item_qty"] if production_item else 0










