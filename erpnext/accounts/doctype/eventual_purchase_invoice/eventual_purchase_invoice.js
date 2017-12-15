// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Eventual Purchase Invoice", {

    refresh: function (frm) {
        if(frm.doc.docstatus == 1 && frm.doc.outstanding_amount != 0) {
            frm.add_custom_button(__('Payment'), make_payment_entry);
        }
    },

    total_amount: function (frm) {
        frm.set_value("outstanding_amount", frm.doc.total_amount);
    }

});


var make_payment_entry = function() {
		return frappe.call({
			method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry_for_eventual_purchase_invoice",
			args: {
				"docname": cur_frm.doc.name
			},
			callback: function(r) {
				var doclist = frappe.model.sync(r.message);
				frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
			}
		});
}
