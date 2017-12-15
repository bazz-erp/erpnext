frappe.listview_settings['Eventual Purchase Invoice'] = {
	add_fields: ["outstanding_amount"],

	get_indicator: function(doc) {
		if(flt(doc.outstanding_amount) > 0 && doc.docstatus==1) {
				return [__("Unpaid"), "orange", "outstanding_amount,>,0"];

		}
		else if(flt(doc.outstanding_amount)<=0 && doc.docstatus==1) {
			return [__("Paid"), "green", "outstanding_amount,=,0"];
		}
		else {
			return [__("Draft"), "red", "docstatus,=,0"];
		}
	}
};