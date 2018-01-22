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


    def start_operation(self):
        if not self.status == 'Pending':
            frappe.throw(_("Operation cannot be started"))

        production_order = frappe.get_doc("Production Order", self.production_order)

        po_operation = filter(lambda op: op.completion == self.name, production_order.operations)[0]

        previous_op_status = frappe.db.sql("""select status from `tabProduction Order Operation` where 
parent = %s AND idx = %s""", (self.production_order, po_operation.idx - 1))

        if previous_op_status and previous_op_status[0][0] != 'Completed':
            frappe.throw(_("Previous Operation must be completed"))

        self.db_set("status", "In Process")
        po_operation.db_set("status", "In Process")

    def finish_operation(self):
        if not self.status == 'In Process':
            frappe.throw(_("Operation must be started to finish it"))

        production_order = frappe.get_doc("Production Order", self.production_order)

        po_operation = filter(lambda op: op.completion == self.name, production_order.operations)[0]

        self.db_set("status", "Completed")
        po_operation.db_set("status", "Completed")

        next_operation = filter(lambda op: op.idx == po_operation.idx + 1, production_order.operations)

        if next_operation:
            next_operation[0].db_set("status", "Pending")
            next_operation_completion = frappe.get_doc("Operation Completion", next_operation[0].completion)
            next_operation_completion.db_set("status", "Pending")
















