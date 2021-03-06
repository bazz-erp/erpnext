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

        items_supplied = self.remove_empty_items(items_supplied)
        if not items_supplied:
            return

        production_order = frappe.get_doc("Production Order", self.production_order)

        if self.status == "Pending" and not workshop:
            frappe.throw(_("Workshop is mandatory when sending materials for the first time"))

        po_operation = filter(lambda op: op.completion == self.name, production_order.operations)[0]

        # supplied qty of production item cannot be greather than work in progress qty
        if items_supplied.get(production_order.production_item, 0) > production_order.work_in_progress_qty:

            frappe.throw(_("Available qty of production item is {0}").format(production_order.work_in_progress_qty))

        if self.status == 'Pending':
            self.db_set("status", "In Process")
            self.db_set("workshop", workshop)
            self.db_set("start_date", frappe.utils.nowdate())

            po_operation.db_set("status", "In Process")
            po_operation.db_set("workshop", workshop)
            production_order.update_status()


        for item_code, item_qty in items_supplied.items():
            items_supplied_detail = self.get("items_supplied", {"item_code": item_code})
            if not items_supplied_detail:
                item_name = frappe.get_value("Item", {"name": item_code}, "item_name")
                self.append("items_supplied", {"item_code": item_code, "item_qty": item_qty, "item_name": item_name})
                self.save()
            else:
                items_supplied_detail[0].db_set("item_qty", items_supplied_detail[0].item_qty + item_qty)


        self.transfer_material_to_workshop(production_order, items_supplied)
        production_order.update_required_items()


    def remove_empty_items(self, items_collection):
        return {code: qty for code, qty in items_collection.items() if qty != 0}

    def finish_operation(self, operating_cost, items_received):
        items_received = self.remove_empty_items(items_received)
        if not items_received:
            return

        if not self.status == 'In Process':
            frappe.throw(_("Operation must be started to send materials."))

        if operating_cost is None:
            frappe.throw(_("Operation cost is mandatory"))

        production_order = frappe.get_doc("Production Order", self.production_order)
        production_item_received_qty = flt(items_received.get(production_order.production_item, 0))

        for item_code, item_qty in items_received.items():

            item_name = frappe.get_value("Item", {"name": item_code}, "item_name")
            item_available_qty = self.calculate_item_remaining_qty(item_code)

            if item_qty > item_available_qty:
                frappe.throw(_("Available qty of {0} is {1}").format(item_name, item_available_qty))

            items_received_detail = self.get("items_received", {"item_code": item_code})
            if not items_received_detail:
                self.append("items_received", {"item_code": item_code, "item_qty": item_qty, "item_name": item_name})
                self.save()
            else:
                items_received_detail[0].db_set("item_qty", items_received_detail[0].item_qty + item_qty)

        self.db_set("total_amount", self.total_amount + operating_cost)
        self.db_set("total_received_qty", self.total_received_qty + production_item_received_qty)

        # Get the operation row in production order to update the status and the operating cost
        production_order_operation = filter(lambda op: op.completion == self.name, production_order.operations)[0]
        production_order_operation.db_set("total_operating_cost", production_order_operation.total_operating_cost + operating_cost)

        production_order.db_set("operations_cost", production_order.operations_cost + operating_cost)
        production_order.db_set("total_cost", production_order.total_cost + operating_cost)

        if (self.total_received_qty >= production_order.qty):
            self.db_set("status", "Completed")
            production_order_operation.db_set("status", "Completed")
            production_order.update_status()

        self.receive_material_from_workshop(production_order, items_received, operating_cost)
        production_order.update_required_items()

    def transfer_material_to_workshop(self, production_order, items_supplied):
        stock_entry = self.create_stock_entry(production_order)
        stock_entry.purpose = "Manufacturer Shipping"
        stock_entry.title = _("Material Transfer to Workshop")
        workshop_warehouse = self.get_workshop_warehouse(production_order.company)


        for item_code, item_qty in items_supplied.items():
            stock_entry_detail = {"item_code": item_code, "qty": item_qty}

            # raw materials are taken from warehouse defined in required_items table
            # production item is get from 'work in progress' warehouse
            if item_code == production_order.production_item:
                stock_entry_detail["s_warehouse"] = production_order.wip_warehouse
                # update production item qty in 'work in progress' warehouse that corresponds to this po order
                production_order.db_set("work_in_progress_qty", production_order.work_in_progress_qty - item_qty)
            else:
                stock_entry_detail["s_warehouse"] = production_order.get("required_items", {"item_code": item_code})[0].source_warehouse

            stock_entry_detail["t_warehouse"] = workshop_warehouse
            stock_entry.append("items", stock_entry_detail)

        stock_entry.submit()


    def receive_material_from_workshop(self, production_order, items_received, operation_cost):
        stock_entry = self.create_stock_entry(production_order)
        stock_entry.purpose = "Manufacturer Receipt"

        stock_entry.title = _("Receive Material from Workshop")

        for item_code, item_qty in items_received.items():
            product_dict = {"item_code": item_code, "qty": item_qty}

            if item_code == production_order.production_item:
                """production item must be transferred to 'work in progress' warehouse. 
                    If this item was sent, it must be deducted from the workshop's warehouse. 
                    Else, if the workshop origin the product, source warehouse is null"""
                product_dict["s_warehouse"] = self.get_workshop_warehouse(production_order.company) if self.is_production_item_supplied(production_order.production_item) else None
                product_dict["t_warehouse"] = production_order.wip_warehouse

                # set operation cost per unit
                # total operation cost is automatically calculated in stock entry
                product_dict["basic_rate"] = operation_cost / item_qty

                production_order.db_set("work_in_progress_qty", production_order.work_in_progress_qty + item_qty)
                self.consume_raw_materials(stock_entry, production_order, item_qty)
            else:
                # raw materials must be transferred to its production warehouse
                product_dict["s_warehouse"] = self.get_workshop_warehouse(production_order.company)
                product_dict["t_warehouse"] = production_order.get("required_items", {"item_code": item_code})[0].source_warehouse

            stock_entry.append("items", product_dict)

        stock_entry.submit()
        production_order.update_production_order_qty()

    def get_workshop_warehouse(self, company):
        return frappe.get_doc("Supplier", self.workshop).get_company_warehouse(company)


    def is_production_item_supplied(self, production_item):
        production_item_supplied = self.get("items_supplied", {"item_code": production_item})
        return production_item_supplied and production_item_supplied[0].item_qty != 0


    def consume_raw_materials(self,stock_entry, production_order, production_item_qty):
        """the amount of each material in the workshop used to producte production_item_qty units of production item
        is transferred to a Null warehouse to the represent the use of the material"""
        for item in self.items_supplied:
            item_qty_in_workshop = self.get_item_qty_in_workshop(item.item_code)
            if item.item_code != production_order.production_item and item_qty_in_workshop > 0:

                # get required qty of item for the whole production order
                item_total_required_qty = production_order.get("required_items", {"item_code": item.item_code})[0].required_qty

                # calculate required qty to produce production_item_qty items
                item_used_qty = (production_item_qty * item_total_required_qty) / production_order.qty

                if item_used_qty > item_qty_in_workshop:
                    frappe.throw(_("{0} units of {1} are needed to produce "
                                   "{2} units of {3}. Workshop has {4}").format(item_used_qty, item.item_name,
                                                                                production_item_qty, production_order.production_item_name, item_qty_in_workshop))
                stock_entry.append("items", {"item_code": item.item_code,
                                         "qty": item_used_qty,
                                         "s_warehouse": self.get_workshop_warehouse(production_order.company)})


    def create_stock_entry(self, production_order):
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.production_order = production_order.name
        stock_entry.company = production_order.company
        stock_entry.from_bom = 0
        stock_entry.operation = self.name
        return stock_entry

    def calculate_item_remaining_qty(self, item_code):
        production_order = frappe.get_doc("Production Order", self.production_order)
        # if the item is the production item and it was not previously sent to the workshop, its remaining qty is based on raw materials
        if item_code == production_order.production_item and not (self.is_production_item_supplied(production_order.production_item)):
            return self.calculate_production_item_remaining_qty_based_on_raw_materials()
        else:
            return self.get_item_qty_in_workshop(item_code)


    def calculate_production_item_remaining_qty_based_on_raw_materials(self):
        """For each raw material, considering its availability in the workshop, calculate how many products can be manufactured.
           The highest value obtained (removing the amount already received)
           corresponds to the amount of production item that the workshop owes"""

        production_order = frappe.get_doc("Production Order", self.production_order)
        bom = frappe.get_doc("BOM", production_order.bom_no)
        max_production_item_qty = 0
        for item in self.items_supplied:
            if item.item_code != production_order.production_item:
                item_qty_in_workshop = self.get_item_qty_in_workshop(item.item_code)
                item_bom_qty = bom.get("items", {"item_code": item.item_code})[0].qty
                production_item_qty = (item_qty_in_workshop * bom.quantity) / item_bom_qty
                if production_item_qty > max_production_item_qty:
                    max_production_item_qty = int(production_item_qty)

        production_item_received = self.get("items_received", {"item_code": production_order.production_item})
        production_item_received_qty = production_item_received[0].item_qty if production_item_received else 0
        return max_production_item_qty - production_item_received_qty

    def get_item_qty_in_workshop(self, item_code):
        """Obtains the amount of a specific material that the workshop possesses dedicated to this operation."""
        sent_qty = self.get("items_supplied", {"item_code": item_code})[0].item_qty if self.get("items_received", {"item_code": item_code}) else 0
        received_qty = self.get("items_received", {"item_code": item_code})[0].item_qty if self.get("items_received", {"item_code": item_code}) else 0
        return sent_qty - received_qty


    # empty method to guarantee polymorphism when updating outstanding amount in gl entry
    def set_status(self, update=True):
        pass


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
    return operation.calculate_item_remaining_qty(production_order.production_item)

def get_production_item_available_qty(production_order, production_order_operation):
    # operation has no predecessor
    if production_order_operation.idx == 1:
        return 0

    previous_operation_id = filter(lambda op: (op.idx + 1) == production_order_operation.idx, production_order.operations)[0].completion
    available_materials = get_available_materials(production_order_operation.completion, previous_operation_id)
    production_item = filter(lambda item: item["item_code"] == production_order.production_item, available_materials)
    return production_item[0]["item_qty"] if production_item else 0










