// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Pending Products"] = {
	"filters": [
	  {
			"fieldname":"item",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
	  },
	  {
			"fieldname":"workshop",
			"label": __("Workshop"),
			"fieldtype": "Link",
			"options": "Supplier",
			"get_query": function () {
			    return {
			        "filters": {"supplier_type": "Taller"}
			    };
			}
	  },

	]
}
