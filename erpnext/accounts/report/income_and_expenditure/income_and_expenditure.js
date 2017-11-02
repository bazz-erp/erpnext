// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.query_reports["Income and Expenditure"] = {
	"filters": [
		{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
			"width": "60px"
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
			"width": "60px"
		},
		{
			"fieldname":"account",
			"label": __("Account"),
			"fieldtype": "Link",
			"options": "Account",
			"get_query": function() {
				var company = frappe.query_report_filters_by_name.company.get_value();
				return {
					"doctype": "Account",
					"filters": {
						"company": company,
						"account_type": ["in", ["Bank", "Cash"]],
						"is_group": 0
					}
				}
			}
		}
	],
	"formatter": function (row, cell, value, columnDef, dataContext, default_formatter) {

	    value = default_formatter(row, cell, value, columnDef, dataContext);

	    if (!dataContext[__("Voucher No")] && !dataContext[__("Voucher Type")]
			&& dataContext[__("Account")] != __("Balance")) {

	        if (dataContext[__("Account")] == __("Totals")) {
                value = "<span style='font-weight:bold;font-size:larger'>" + value + "</span>";
            }
            else {
                value = "<span style='font-weight:bold'>" + value + "</span>";
	        }

	    }

	    return value;
	}
}
