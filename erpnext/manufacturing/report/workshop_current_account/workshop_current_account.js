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
	]
}
