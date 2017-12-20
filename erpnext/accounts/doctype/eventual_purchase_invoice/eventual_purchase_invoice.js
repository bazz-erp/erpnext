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
    },

    taxed_amount_21: function (frm) {
        if (frm.doc.taxed_amount_21 !== undefined) {
            frm.set_value("iva_21", frm.doc.taxed_amount_21 * 0.21);
            frm.refresh_field("iva_21");
            frm.events.set_total_amount(frm);
        }
    },

    taxed_amount_10: function (frm) {
        if (frm.doc.taxed_amount_10 !== undefined) {
            frm.set_value("iva_10", frm.doc.taxed_amount_10 * 0.105);
            frm.refresh_field("iva_10");
            frm.events.set_total_amount(frm);
        }
    },

    taxed_amount_27: function (frm) {
        if (frm.doc.taxed_amount_27 !== undefined) {
            frm.set_value("iva_27", frm.doc.taxed_amount_27 * 0.27);
            frm.refresh_field("iva_27");
            frm.events.set_total_amount(frm);
        }
    },

    exempts: function (frm) {
        frm.events.set_total_amount(frm);
    },

    others: function (frm) {
        frm.events.set_total_amount(frm);
    },

    iva_perception: function (frm) {
        frm.events.set_total_amount(frm);
    },

    ibb_perception: function (frm) {
        frm.events.set_total_amount(frm);
    },

    set_total_amount: function (frm) {
        total_amount = 0;
        var fields = ["taxed_amount_21", "taxed_amount_10", "taxed_amount_27",
            "iva_10", "iva_21", "iva_27", "exempts", "others", "iva_perception", "ibb_perception"];

        $.each(fields, function (i, fieldname) {
            if (frm.get_field(fieldname).value) {
                total_amount += frm.get_field(fieldname).value;
            }
        });

        frm.set_value("total_amount", total_amount);
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
