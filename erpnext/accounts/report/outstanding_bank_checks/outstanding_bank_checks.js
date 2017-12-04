// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Outstanding Bank Checks"] = {
	"filters": [
		{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1,
			"get_query": function () {
				var types = ["A"];
				if(frappe.user_roles.includes("System Manager")){
					types.push("B", "A+B");
                }
                return {
                    "doctype": "Company",
                    "filters": {
                        "type": ["in", types]
                    }
                }
            }
		},
		{
			"fieldname":"customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer",
			"default": "",
			"reqd": 1
		}
	],
	"formatter": function (row, cell, value, columnDef, dataContext, default_formatter) {

	    value = default_formatter(row, cell, value, columnDef, dataContext);

	    if (dataContext[__("Concept")] == __("Total")) {
	    	value = "<span style='font-weight:bold;font-size:larger'>" + value + "</span>";
	    }

	    return value;
	}
}
