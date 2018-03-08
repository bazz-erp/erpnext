from __future__ import unicode_literals
import frappe
from frappe.desk.reportview import *

@frappe.whitelist()
def get_items():
    args = get_form_params()
    price_list_showed = frappe.db.get_single_value("Stock Settings", "default_pricelist")
    args["fields"].append("""(select price_list_rate from `tabItem Price` ip where ip.parent=`tabItem`.`name` and ip.price_list='{}')  as standard_rate""".format(price_list_showed))
    return compress(execute(**args), args = args)