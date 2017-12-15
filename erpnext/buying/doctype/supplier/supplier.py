# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
import frappe.defaults
from frappe import msgprint, _
from frappe.model.naming import make_autoname
from frappe.contacts.address_and_contact import load_address_and_contact, delete_contact_and_address
from erpnext.utilities.transaction_base import TransactionBase
from erpnext.accounts.party import validate_party_accounts, get_dashboard_info, get_timeline_data  # keep this


class Supplier(TransactionBase):
    def get_feed(self):
        return self.supplier_name

    def onload(self):
        """Load address and contacts in `__onload`"""
        load_address_and_contact(self, "supplier")
        self.load_dashboard_info()

    def load_dashboard_info(self):
        info = get_dashboard_info(self.doctype, self.name)
        self.set_onload('dashboard_info', info)


    # autoname was redefined in Bazz
    """def autoname(self):
        supp_master_name = frappe.defaults.get_global_default('supp_master_name')
        if supp_master_name == 'Supplier Name':
            self.name = self.supplier_name
        else:
            self.name = make_autoname(self.naming_series + '.#####')"""

    def autoname(self):
        self.name = str(self.code) + " - " + self.supplier_name

    def on_update(self):
        if not self.naming_series:
            self.naming_series = ''

    def validate(self):
        # validation for Naming Series mandatory field...
        if frappe.defaults.get_global_default('supp_master_name') == 'Naming Series':
            if not self.naming_series:
                msgprint(_("Series is mandatory"), raise_exception=1)

        validate_party_accounts(self)
        validate_code(self)

    def on_trash(self):
        delete_contact_and_address('Supplier', self.name)

    def after_rename(self, olddn, newdn, merge=False):
        if frappe.defaults.get_global_default('supp_master_name') == 'Supplier Name':
            frappe.db.set(self, "supplier_name", newdn)


@frappe.whitelist()
def get_supplier_code():
    return frappe.db.sql("""SELECT (MAX(CAST(code AS INTEGER)) + 1) as code  FROM `tabSupplier`""", as_dict=1)

def validate_code(supplier):
    supplier.code = str(supplier.code).lstrip("0") if supplier.code else get_supplier_code()
    result = frappe.db.sql("""SELECT code, name FROM `tabSupplier` WHERE code=%s""", supplier.code, as_dict=1)
    match = [s for s in result if s.name == supplier.name]
    if len(result) != 0 and len(match) == 0:
        frappe.throw(_("""Code is already taken. Please choose a new one"""))