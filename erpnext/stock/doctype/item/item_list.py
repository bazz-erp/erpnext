import frappe
from frappe.desk.reportview import *

@frappe.whitelist()
def get_items():
    args = get_form_params()
    args["fields"].append("""(select price_list_rate from `tabItem Price` ip where ip.parent=`tabItem`.`name` and ip.price_list='Compra Estandar')  as standard_rate""")
    return compress(execute(**args), args = args)