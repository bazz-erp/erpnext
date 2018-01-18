// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Operation Completion', {

	refresh: function(frm) {
		if (frm.doc.status == 'Pending') {
			frm.add_custom_button(__("Start"), function () {
				start_operation(frm);
				frappe.set_route("Form", "Production Order", frm.doc.production_order);
            });
		}

		if (frm.doc.status == 'In Process') {
			frm.add_custom_button(__("Finish"), function () {
				finish_operation(frm);
                frappe.set_route("Form", "Production Order", frm.doc.production_order);
            });
		}
	}
});

var start_operation = function (frm) {
	if (!frm.doc.workshop) {
		frappe.throw(__("Workshop is mandatory to Start Operation"))
	}
	frappe.call({
		method: "start_operation",
		doc: frm.doc,
		callback: function (r) {

        }
	});
}

var finish_operation = function (frm) {
	if (!frm.doc.operating_cost) {
		frappe.throw(__("Operating Cost is mandatory to Finish Operation"))
	}
	frappe.call({
		method: "finish_operation",
		doc: frm.doc,
		callback: function (r) {

        }
	});
}
