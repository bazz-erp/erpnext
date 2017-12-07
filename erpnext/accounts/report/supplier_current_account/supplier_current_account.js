// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Supplier Current Account"] = {
	"filters": [
		{
			"fieldname":"supplier",
			"label": __("Suppler"),
			"fieldtype": "Link",
			"options": "Supplier",
			"reqd": 1,
			"width": "60px"
		},

	],
	"formatter": function (row, cell, value, columnDef, dataContext, default_formatter) {

	    value = default_formatter(row, cell, value, columnDef, dataContext);


	    if (dataContext[__("Voucher Type")] == __("Total")) {
	    	value = "<span style='font-weight:bold;font-size:larger'>" + value + "</span>";
	    }

	    return value;
	}
}
