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
	  {
			"fieldname":"customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer",
	  },
	  {
			"fieldname":"group_by",
			"label": __("Group By"),
			"fieldtype": "Select",
			"options": "Workshop\nItem\nCustomer",
			"default": "Workshop"
	  }
	],
	"formatter": function (row, cell, value, columnDef, dataContext, default_formatter) {
	    value = default_formatter(row, cell, value, columnDef, dataContext);
        debugger;
	    if (!dataContext[__("Operation")] && !dataContext[__("Production Order")]) {
	        value = "<span style='font-weight:bold;font-size:larger'>" + value + "</span>";
	    }

	    return value;
	}
}
