// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Supplier", {
	onload: function (frm) {
		if(!frm.doc.code){
			set_supplier_code();
		}
		frm.make_methods = {
			"Payment Entry": function (frm) {
				frappe.model.with_doctype("Payment Entry", function() {
					var new_doc = frappe.model.get_new_doc("Payment Entry");
					new_doc.party_type = "Supplier";
					new_doc.payment_type = "Pay";
					frappe.set_route('Form', "Payment Entry", new_doc.name);
				});
            }
		};
    },
	setup: function (frm) {
		frm.set_query('default_price_list', { 'buying': 1 });
		frm.set_query('account', 'accounts', function (doc, cdt, cdn) {
			var d = locals[cdt][cdn];
			return {
				filters: {
					'account_type': 'Payable',
					'company': d.company,
					"is_group": 0
				}
			}
		});
	},
	refresh: function (frm) {
		frappe.dynamic_link = { doc: frm.doc, fieldname: 'name', doctype: 'Supplier' }

		if (frappe.defaults.get_default("supp_master_name") != "Naming Series") {
			frm.toggle_display("naming_series", false);
		} else {
			erpnext.toggle_naming_series();
		}

		if (frm.doc.__islocal) {
			hide_field(['address_html','contact_html']);
			frappe.contacts.clear_address_and_contact(frm);
		}
		else {
			unhide_field(['address_html','contact_html']);
			frappe.contacts.render_address_and_contact(frm);

			// custom buttons
			frm.add_custom_button(__('Accounting Ledger'), function () {
				frappe.set_route('query-report', 'General Ledger',
					{ party_type: 'Supplier', party: frm.doc.name });
			});
			frm.add_custom_button(__('Accounts Payable'), function () {
				frappe.set_route('query-report', 'Accounts Payable', { supplier: frm.doc.name });
			});

			frm.add_custom_button(__('Current Account'), function () {
				if (frm.doc.supplier_type == "Taller") {
				   frappe.set_route('query-report', 'Workshop Current Account', { workshop: frm.doc.name });
				}
				else {
				   frappe.set_route('query-report', 'Supplier Current Account', { supplier: frm.doc.name });
				}

			});

			// indicators
			erpnext.utils.set_party_dashboard_indicators(frm);
		}
	},
});

var set_supplier_code = function () {
	frappe.call({
        method: "erpnext.buying.doctype.supplier.supplier.get_supplier_code",
        args: {},
        callback: function (r, rt) {
            if(r.message){
                me.frm.set_value("code", r.message[0].code)
			    me.frm.refresh_fields();
            }
        }
	});
}
