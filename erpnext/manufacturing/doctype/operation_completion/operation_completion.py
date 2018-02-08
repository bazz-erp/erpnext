# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class OperationCompletion(Document):

    def autoname(self):
        self.name = self.production_order + " - " + self.operation

    def validate(self):
        for field in ["operation", "production_order"]:
            if not self.get(field):
                frappe.throw(_("{0} is mandatory in Operation Completion").format(self.meta.get_label(field)))


    def start_operation(self, workshop, items_supplied):
        if self.status == 'Completed':
           frappe.throw(_("You cant send anymore, the operation is already completed."))
        production_order = frappe.get_doc("Production Order", self.production_order)

        # ACUMULAR EN LA TABLA
        # REALIZAR EL MOVIMIENTO DE STOCK

        if self.status == 'Pending':
            po_operation = filter(lambda op: op.completion == self.name, production_order.operations)[0]
            self.db_set("status", "In Process")
            self.db_set("workshop",workshop)
            po_operation.db_set("status", "In Process")

        # Clear items whose transferred qty is 0
        items_supplied = filter(lambda item: item.qty != 0, items_supplied)

        # REALIZAR EL MOVIMIENTO DE STOCK
        self.transfer_material_to_workshop(production_order, items_supplied)

        # update total qty supplied to the workshop in items supplied Table
        for item in items_supplied:
            items_supplied_detail = self.get("items_supplied", {"item_code": item.item})
            if not items_supplied_detail:
                self.append("items_supplied", {"item_code": item, "item_qty": item.qty})
                self.save()
            else:
                items_supplied_detail[0].qty += item.qty
                items_supplied_detail[0].save()


    def finish_operation(self, operating_cost, items_received):
        if not self.status == 'In Process':
            frappe.throw(_("Operation must be started to send materials."))

        # agarrar la canitdad que recibo
        received_qty = items_received[0].get('qty', 0)
        print(items_received[0], received_qty)
        if received_qty <= 0:
            frappe.throw(_("Quantity must be greater than 0."))

        production_order = frappe.get_doc("Production Order", self.production_order)
        po_operation = filter(lambda op: op.completion == self.name, production_order.operations)[0]

        # costos
        self.db_set("operating_cost", self.operating_cost + operating_cost)

        # la sumo a un contador de la operación
        self.db_set("total_received_qty", self.total_received_qty + received_qty)

        # REALIZAR EL MOVIMIENTO DE STOCK
        # si la el contador es igual a la cantidad a fabricar la termino
        if (self.total_received_qty == production_order.qty):
            self.db_set("status", "Completed")
            po_operation.db_set("status", "Completed")

    def transfer_material_to_workshop(self, production_order, items_supplied):
        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.purpose = "Material Transfer"
        stock_entry.title = "Material Transfer to Workshop"
        stock_entry.production_order = production_order.name
        stock_entry.company = production_order.company
        stock_entry.from_bom = 0

        workshop_warehouse = frappe.get_doc("Supplier", self.workshop).workshop_warehouse

        stock_entry.from_warehouse = production_order.wip_warehouse
        stock_entry.to_warehouse = workshop_warehouse

        for item in items_supplied:
            stock_entry.append("items", {"item_code": item.item, "qty": item.qty})

        stock_entry.submit()








