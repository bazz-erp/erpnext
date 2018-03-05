// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Workshop Current Account"] = {
	"filters": [
       {
			"fieldname":"workshop",
			"label": __("Workshop"),
			"fieldtype": "Link",
			"options": "Supplier",
			"get_query": function () {
			    return {
			        "filters": {"supplier_type": "Taller"}
			    };
			},
			"reqd": 1
	  },
	  {
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
	],
	"formatter": function (row, cell, value, columnDef, dataContext, default_formatter) {
	    value = default_formatter(row, cell, value, columnDef, dataContext);
	    console.log(columnDef);
	    if (columnDef.id == __("Balance")) {
	        value = "<span style='font-weight:bold'>" + value + "</span>";
	    }
	    if (dataContext[__("Operation")] == __("Total")) {
	        value = "<span style='font-weight:bold;font-size:larger'>" + value + "</span>";
	    }
	    return value;
	}
}
