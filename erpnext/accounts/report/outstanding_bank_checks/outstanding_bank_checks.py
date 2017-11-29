# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
    if not filters.get("company"):
        frappe.throw(_("Company is mandatory"))

    data = get_data(filters)
    columns = get_columns()

    return columns, data



def get_columns():
    columns = [_("Payment Date") + ":Date:100",_("Amount") + ":Currency:100",
                _("Bank") + ":Data:150",
                _("Number") + ":Data:150",
               _("Concept") + ":Data:150",
                _("Internal Number") + ":Data:150"]
    return columns


def get_data(filters):
    data = []
    bank_checks = frappe.db.sql("""select payment_date, concept,amount, bank, number, internal_number from `tabBank Check` 
WHERE company=%(company)s and third_party_check=TRUE and used=FALSE and payment_date > CURRENT_DATE""", filters, as_dict=1)
    for check in bank_checks:
        data.append([check.payment_date, check.amount, check.bank, check.number, check.concept, check.internal_number])

    return data