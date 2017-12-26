# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import json

class ItemAttributeValue(Document):
	pass



@frappe.whitelist()
def get_attributes_values(attributes):
    attributes_names = json.loads(attributes)
    attributes_dict = {}

    result = frappe.db.sql("""select parent as attribute_name, attribute_value from `tabItem Attribute Value`
            where parent in {attributes}""".format(attributes=get_attributes_str(attributes_names)), as_dict =1)

    for row in result:
        if attributes_dict.get(row.attribute_name) is None:
            attributes_dict[row.attribute_name] = []
        attributes_dict[row.attribute_name].append(row.attribute_value)

    return attributes_dict

def get_attributes_str(attributes):
    if attributes:
        attributes = map(lambda attr: "'" + attr + "'", attributes)
        return "(" + ",".join(attributes) + ")"
    else:
        return "()"


