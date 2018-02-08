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

        # REALIZAR EL MOVIMIENTO DE STOCK

        if self.status == 'Pending':
            po_operation = filter(lambda op: op.completion == self.name, production_order.operations)[0]
            self.db_set("status", "In Process")
            po_operation.db_set("status", "In Process")

    def finish_operation(self, operating_cost, items_received):
        # agarrar la canitdad que recibo
        qty = items_received[0].qty
        if qty <= 0:
            frappe.throw(_("Quantity must be greater than 0."))

        if not self.status == 'In Process':
            frappe.throw(_("Operation must be started to send materials."))

        production_order = frappe.get_doc("Production Order", self.production_order)

        po_operation = filter(lambda op: op.completion == self.name, production_order.operations)[0]


        # la sumo a un contador de la operación

        # REALIZAR EL MOVIMIENTO DE STOCK
        # si la el contador es igual a la cantidad a fabricar la termino
        if ():
            self.db_set("status", "Completed")
            po_operation.db_set("status", "Completed")







