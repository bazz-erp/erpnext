// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
{% include "erpnext/public/js/controllers/accounts.js" %}

var event_bound = false;
var doc_counter;
var check_counter;

frappe.ui.form.on('Payment Entry', {

    onload: function (frm) {
        if (frm.doc.__islocal) {
            if (!frm.doc.paid_from) frm.set_value("paid_from_account_currency", null);
            if (!frm.doc.paid_to) frm.set_value("paid_to_account_currency", null);
        }
        set_up_payment_lines(frm);

        frm.get_field('third_party_bank_checks').grid.editable_fields = [
            {fieldname: 'payment_date', columns: 2},
            {fieldname: 'amount', columns: 2},
            {fieldname: 'bank', columns: 2},
            {fieldname: 'number', columns: 2},
            {fieldname: 'internal_number', columns: 2}
        ];

        frm.get_field('outgoing_bank_checks').grid.editable_fields = [
            {fieldname: 'payment_date', columns: 2},
            {fieldname: 'amount', columns: 2},
            {fieldname: 'account', columns: 2},
            {fieldname: 'number', columns: 2}
        ];

        frm.get_field('third_party_documents').grid.editable_fields = [
            {fieldname: 'date', columns: 2},
            {fieldname: 'amount', columns: 2},
            {fieldname: 'client_detail', columns: 2},
            {fieldname: 'internal_number', columns: 2}
        ];

        frm.get_field('documents').grid.editable_fields = [
            {fieldname: 'date', columns: 2},
            {fieldname: 'amount', columns: 2},
            {fieldname: 'internal_number', columns: 2}
        ];

	    if (frm.doc.outgoing_bank_checks && frm.doc.outgoing_bank_checks.length != 0) {
	        frm.set_df_property("outgoing_bank_checks","hidden" ,false);
	    }

	    if (frm.doc.documents && frm.doc.documents.length != 0) {
            frm.set_df_property("documents", "hidden", false);
        }

	    frm.refresh_fields();

	    /* Hide add button on modes of payment table */
	    $( 'div[data-fieldname="lines"] .grid-add-row').hide();

        /* Reset the checks and documents autoincremental counter */
        doc_counter = 0;
        check_counter = 0;

        /* Set concept if payment come from other form */
        frm.events.set_concept(frm);

    },

    setup: function (frm) {
        /**
         * paid_from field is used only in Internal Transfer payment type
         */
        frm.set_query("paid_from", function () {

            return {
                query: "erpnext.controllers.queries.get_accounts_ordered",
                filters: {
                    "account_type": ["in", ["Bank", "Cash", "Check Wallet", "Document Wallet"]],
                    "is_group": 0,
                    "company": frm.doc.company
                }
            }
        });

        frm.set_query("party_type", function () {
            return {
                "filters": {
                    "name": ["in", ["Customer", "Supplier", "Employee"]],
                }
            }
        });

        frm.set_query("paid_to", function () {
             /**
              * paid_to field is used only in Internal Transfer payment type
              */

            return {
                "query": "erpnext.controllers.queries.get_accounts_ordered",
                filters: {
                    "account_type": ["in", ["Bank", "Cash"]],
                    "is_group": 0,
                    "company": frm.doc.company
                }
            }
        });

        frm.set_query("account", "deductions", function () {
            return {
                filters: {
                    "is_group": 0,
                    "company": frm.doc.company
                }
            }
        });

        frm.set_query("cost_center", "deductions", function () {
            return {
                filters: {
                    "is_group": 0,
                    "company": frm.doc.company
                }
            }
        });

        frm.set_query("reference_doctype", "references", function () {
            if (frm.doc.party_type == "Customer") {
                var doctypes = ["Sales Order", "Sales Invoice", "Journal Entry"];
            } else if (frm.doc.party_type == "Supplier") {
                var doctypes = ["Purchase Order", "Purchase Invoice", "Journal Entry"];
            } else if (frm.doc.party_type == "Employee") {
                var doctypes = ["Expense Claim", "Journal Entry"];
            } else {
                var doctypes = ["Journal Entry"];
            }

            return {
                filters: {"name": ["in", doctypes]}
            };
        });

        frm.set_query("reference_name", "references", function (doc, cdt, cdn) {
            child = locals[cdt][cdn];
            filters = {"docstatus": 1, "company": doc.company};
            party_type_doctypes = ['Sales Invoice', 'Sales Order', 'Purchase Invoice',
                'Purchase Order', 'Expense Claim'];

            if (in_list(party_type_doctypes, child.reference_doctype)) {
                filters[doc.party_type.toLowerCase()] = doc.party;
            }

            if (child.reference_doctype == "Expense Claim") {
                filters["status"] = "Approved";
                filters["is_paid"] = 0;
            }

            return {
                filters: filters
            };
        });

        frm.set_query("account", "outgoing_bank_checks", function () {
            return {
                filters: {
                    "is_group": 0,
                    "company": frm.doc.company,
                    "account_type": "Bank"
                }
            }
        });

    },

    refresh: function (frm) {
        if (frm.doc.docstatus == 1) {
            //hide mode of payment amounts section
            frm.set_df_property("mode_of_payment_totals_section", "hidden", true);
        }

        if (is_expenditure(frm) || frm.doc.payment_type == "Internal Transfer") {
            if (frm.doc.selected_third_party_bank_checks &&
            frm.doc.selected_third_party_bank_checks != 0) {

                show_selected_third_party_checks(frm);
            }
            if (frm.doc.selected_third_party_documents &&
                frm.doc.selected_third_party_documents != 0) {

                show_selected_third_party_documents(frm);
            }
            // hide check amounts section
            frm.set_df_property("bank_checks_section", "hidden", true);
        }

        else {
            if (frm.doc.third_party_bank_checks && frm.doc.third_party_bank_checks != 0) {
                show_new_third_party_checks(frm);
            }

            if (frm.doc.third_party_documents && frm.doc.third_party_documents != 0) {
                show_new_third_party_documents(frm);
            }
        }

        frm.toggle_display("bank_checks_average_days_section", is_expenditure(frm) && (frm.doc.selected_third_party_bank_checks.length >0
            || frm.doc.outgoing_bank_checks.length > 0));

        frm.set_df_property("documents_section", "hidden", true);



        erpnext.hide_company();
        frm.events.hide_unhide_fields(frm);
        frm.events.set_dynamic_labels(frm);
        frm.events.show_general_ledger(frm);
    },

    company: function (frm) {
        frm.events.hide_unhide_fields(frm);
        frm.events.set_dynamic_labels(frm);
    },

    hide_unhide_fields: function (frm) {
        var company_currency = frm.doc.company ? frappe.get_doc(":Company", frm.doc.company).default_currency : "";

        /** Disabled
         frm.toggle_display("source_exchange_rate",
         (frm.doc.paid_amount && frm.doc.paid_from_account_currency != company_currency));


         frm.toggle_display("target_exchange_rate", (frm.doc.received_amount &&
         frm.doc.paid_to_account_currency != company_currency &&
         frm.doc.paid_from_account_currency != frm.doc.paid_to_account_currency));


         //frm.toggle_display("base_paid_amount", frm.doc.paid_from_account_currency != company_currency);

         frm.toggle_display("base_received_amount", (frm.doc.paid_to_account_currency != company_currency &&
         frm.doc.paid_from_account_currency != frm.doc.paid_to_account_currency)); */

        frm.toggle_display("received_amount", (frm.doc.payment_type == "Internal Transfer" /*||
			frm.doc.paid_from_account_currency != frm.doc.paid_to_account_currency*/))


        frm.toggle_display(["base_total_allocated_amount"],
            (frm.doc.paid_amount && frm.doc.received_amount && frm.doc.base_total_allocated_amount &&
                ((frm.doc.payment_type == "Receive" && frm.doc.paid_from_account_currency != company_currency) ||
                    (frm.doc.payment_type == "Pay" && frm.doc.paid_to_account_currency != company_currency))));


        var party_amount = frm.doc.payment_type == "Receive" ?
            frm.doc.paid_amount : frm.doc.received_amount;

        frm.toggle_display("write_off_difference_amount", (frm.doc.difference_amount && frm.doc.party &&
            (frm.doc.paid_from_account_currency == frm.doc.paid_to_account_currency) &&
            (frm.doc.total_allocated_amount > party_amount)));

        frm.toggle_display("set_exchange_gain_loss",
            (frm.doc.paid_amount && frm.doc.received_amount && frm.doc.difference_amount &&
                (frm.doc.paid_from_account_currency != company_currency ||
                    frm.doc.paid_to_account_currency != company_currency)));

        frm.refresh_fields();
    },

    set_dynamic_labels: function (frm) {
        var company_currency = frm.doc.company ? frappe.get_doc(":Company", frm.doc.company).default_currency : "";

        frm.set_currency_labels(["base_paid_amount", "base_received_amount", "base_total_allocated_amount",
            "difference_amount"], company_currency);

        // Paid amount always is in company currency. Internal Transfer has other label to paid_amount field
        if (frm.doc.payment_type != "Internal Transfer") {
            frm.set_currency_labels(["paid_amount"], company_currency);
        }


        frm.set_currency_labels(["received_amount"], company_currency);

        var party_account_currency = frm.doc.payment_type == "Receive" ?
            frm.doc.paid_from_account_currency : frm.doc.paid_to_account_currency;

        frm.set_currency_labels(["total_allocated_amount", "unallocated_amount"], party_account_currency);

        var currency_field = (frm.doc.payment_type == "Receive") ? "paid_from_account_currency" : "paid_to_account_currency"
        frm.set_df_property("total_allocated_amount", "options", currency_field);
        frm.set_df_property("unallocated_amount", "options", currency_field);
        frm.set_df_property("party_balance", "options", currency_field);

        frm.set_currency_labels(["total_amount", "outstanding_amount", "allocated_amount"],
            party_account_currency, "references");

        frm.set_currency_labels(["amount"], company_currency, "deductions");

        cur_frm.set_df_property("source_exchange_rate", "description",
            ("1 " + frm.doc.paid_from_account_currency + " = [?] " + company_currency));

        cur_frm.set_df_property("target_exchange_rate", "description",
            ("1 " + frm.doc.paid_to_account_currency + " = [?] " + company_currency));


        //Set company currency to paid_amount in payment line
        frm.set_currency_labels(["paid_amount"], company_currency, "lines");


        frm.refresh_fields();
    },

    show_general_ledger: function (frm) {
        if (frm.doc.docstatus == 1) {
            frm.add_custom_button(__('Ledger'), function () {
                frappe.route_options = {
                    "voucher_no": frm.doc.name,
                    "from_date": frm.doc.posting_date,
                    "to_date": frm.doc.posting_date,
                    "company": frm.doc.company,
                    group_by_voucher: 0
                };
                frappe.set_route("query-report", "General Ledger");
            }, "fa fa-table");
        }
    },

    payment_type: function (frm) {
        frm.toggle_reqd(["paid_to", "paid_from"], frm.doc.payment_type == "Internal Transfer");

        if (frm.doc.payment_type == "Internal Transfer") {
            $.each(["party", "party_balance", "paid_from", "paid_to",
                "references", "total_allocated_amount"], function (i, field) {
                frm.set_value(field, null);
            });

            // change paid amount label
            frm.set_df_property("paid_amount", "label", __("Transferred Amount") + " (ARS)");

        } else {
            frm.set_currency_labels(["paid_amount"], get_company_currency(frm));
            if (!frm.doc.party) {
                if (is_income(frm)) {
                    frm.set_value("party_type", "Customer");
                    frm.set_df_property("paid_amount", "label", __("Received Amount") + " (ARS)");
                }else{
                    frm.set_df_property("paid_amount", "label", __("Paid Amount") + " (ARS)");
                }
            }
            else {
                frm.events.party(frm);
            }

            if (frm.doc.mode_of_payment)
                frm.events.mode_of_payment(frm);
        }
        /* resets the internal number counters */
        check_counter = 0;
        doc_counter = 0;

        frm.set_value("party_type", null);
        frm.set_value("party", null);
        frm.set_value("references", null);


        /* clear payment lines */
        frm.set_value("lines", null);
        frm.set_value("remaining_amount", null);
        frm.set_value("allocated_to_mode_of_payment_amount", null);

        /* clear tables */
        frm.set_value("outgoing_bank_checks", null);
        frm.set_value("documents", null);
        frm.set_value("third_party_bank_checks", null);
        frm.set_value("third_party_documents", null);
        frm.set_value("selected_third_party_documents", null);
        frm.set_value("selected_third_party_bank_checks", null);

        /* hide tables */
        frm.toggle_display("bank_checks_section", false);
        frm.toggle_display("documents_section", false);
        frm.toggle_display("third_party_bank_checks_section", false);
        frm.toggle_display("third_party_documents_section", false);

        /* set the wallets read only if the payment is an expenditure */
        frm.set_df_property("third_party_bank_checks", "read_only", is_expenditure(frm));
        frm.refresh_field("third_party_bank_checks");
        frm.set_df_property("third_party_documents", "read_only", is_expenditure(frm));
        frm.refresh_field("third_party_documents");

        set_up_payment_lines(frm);
        frm.refresh_fields();

    },

    party_type: function (frm) {
        if (frm.doc.party) {
            $.each(["party", "party_balance", "paid_from", "paid_to",
                    "paid_from_account_currency", "paid_from_account_balance",
                    "paid_to_account_currency", "paid_to_account_balance",
                    "references", "total_allocated_amount"],
                function (i, field) {
                    frm.set_value(field, null);
                })
        }
    },

    party: function (frm) {
        if (frm.doc.payment_type && frm.doc.party_type && frm.doc.party) {
            if (!frm.doc.posting_date) {
                frappe.msgprint(__("Please select Posting Date before selecting Party"))
                frm.set_value("party", "");
                return;
            }

            frm.set_party_account_based_on_party = true;


            return frappe.call({
                method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_party_details",
                args: {
                    company: frm.doc.company,
                    party_type: frm.doc.party_type,
                    party: frm.doc.party,
                    date: frm.doc.posting_date
                },
                callback: function (r, rt) {
                    if (r.message) {
                        if (frm.doc.payment_type == "Receive") {
                            frm.set_value("paid_from", r.message.party_account);
                            //frm.set_value("paid_from_account_currency", r.message.party_account_currency);
                            frm.set_value("paid_from_account_balance", r.message.account_balance);
                        } else if (frm.doc.payment_type == "Pay") {
                            frm.set_value("paid_to", r.message.party_account);
                            //	frm.set_value("paid_to_account_currency", r.message.party_account_currency);
                            frm.set_value("paid_to_account_balance", r.message.account_balance);
                        }
                        frm.set_value("party_balance", r.message.party_balance);
                        frm.events.hide_unhide_fields(frm);
                        frm.events.set_dynamic_labels(frm);
                        frm.set_party_account_based_on_party = false;

                        frm.events.get_outstanding_documents(frm);
                        frm.events.set_concept(frm);
                    }
                }
            });

        }


    },

    paid_from: function (frm) {

        clear_table(frm, "third_party_bank_checks");
        clear_table(frm, "third_party_documents");

        if (frm.set_party_account_based_on_party) return;

        frm.events.set_account_currency_and_balance(frm, frm.doc.paid_from,
            "paid_from_account_currency", "paid_from_account_balance", function (frm) {
                if (frm.doc.payment_type == "Receive") {
                    frm.events.get_outstanding_documents(frm);
                } else if (frm.doc.payment_type == "Pay") {
                    frm.events.paid_amount(frm);
                }
            }
        );

        if (frm.doc.payment_type == "Internal Transfer") {
            set_up_internal_transfer(frm);
        }
    },

    paid_to: function (frm) {
        if (frm.set_party_account_based_on_party) return;

        frm.events.set_account_currency_and_balance(frm, frm.doc.paid_to,
            "paid_to_account_currency", "paid_to_account_balance", function (frm) {
                if (frm.doc.payment_type == "Pay") {
                    frm.events.get_outstanding_documents(frm);
                } else if (frm.doc.payment_type == "Receive") {
                    frm.events.received_amount(frm);
                }
            }
        );
    },

    set_account_currency_and_balance: function (frm, account, currency_field,
                                                balance_field, callback_function) {
        if (frm.doc.posting_date && account) {
            frappe.call({
                method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_account_details",
                args: {
                    "account": account,
                    "date": frm.doc.posting_date
                },
                callback: function (r, rt) {
                    if (r.message) {
                        frm.set_value(currency_field, r.message['account_currency']);
                        frm.set_value(balance_field, r.message['account_balance']);

                        if (frm.doc.payment_type == "Receive" && currency_field == "paid_to_account_currency") {
                            frm.toggle_reqd(["reference_no", "reference_date"],
                                (r.message['account_type'] == "Bank" ? 1 : 0));
                            if (!frm.doc.received_amount && frm.doc.paid_amount)
                                frm.events.paid_amount(frm);
                        } else if (frm.doc.payment_type == "Pay" && currency_field == "paid_from_account_currency") {
                            frm.toggle_reqd(["reference_no", "reference_date"],
                                (r.message['account_type'] == "Bank" ? 1 : 0));

                            if (!frm.doc.paid_amount && frm.doc.received_amount)
                                frm.events.received_amount(frm);
                        }

                        if (callback_function) callback_function(frm);

                        frm.events.hide_unhide_fields(frm);
                        frm.events.set_dynamic_labels(frm);
                    }
                }
            });
        }
    },

    paid_from_account_currency: function (frm) {
        if (!frm.doc.paid_from_account_currency) return;
        var company_currency = frappe.get_doc(":Company", frm.doc.company).default_currency;

        if (frm.doc.paid_from_account_currency == company_currency) {
            frm.set_value("source_exchange_rate", 1);
        } else if (frm.doc.paid_from) {
            if (in_list(["Internal Transfer", "Pay"], frm.doc.payment_type)) {
                var company_currency = frappe.get_doc(":Company", frm.doc.company).default_currency;
                frappe.call({
                    method: "erpnext.setup.utils.get_exchange_rate",
                    args: {
                        from_currency: frm.doc.paid_from_account_currency,
                        to_currency: company_currency,
                        transaction_date: frm.doc.posting_date
                    },
                    callback: function (r, rt) {
                        frm.set_value("source_exchange_rate", r.message);
                    }
                })
            } else {
                frm.events.set_current_exchange_rate(frm, "source_exchange_rate",
                    frm.doc.paid_from_account_currency, company_currency);
            }
        }
    },

    paid_to_account_currency: function (frm) {
        if (!frm.doc.paid_to_account_currency) return;
        var company_currency = frappe.get_doc(":Company", frm.doc.company).default_currency;

        frm.events.set_current_exchange_rate(frm, "target_exchange_rate",
            frm.doc.paid_to_account_currency, company_currency);
    },

    set_current_exchange_rate: function (frm, exchange_rate_field, from_currency, to_currency) {
        frappe.call({
            method: "erpnext.setup.utils.get_exchange_rate",
            args: {
                transaction_date: frm.doc.posting_date,
                from_currency: from_currency,
                to_currency: to_currency
            },
            callback: function (r, rt) {
                frm.set_value(exchange_rate_field, r.message);
            }
        })
    },

    posting_date: function (frm) {
        frm.events.paid_from_account_currency(frm);
    },

    source_exchange_rate: function (frm) {
        if (frm.doc.paid_amount) {
            frm.set_value("base_paid_amount", flt(frm.doc.paid_amount) * flt(frm.doc.source_exchange_rate));
            if (!frm.set_paid_amount_based_on_received_amount &&
                (frm.doc.paid_from_account_currency == frm.doc.paid_to_account_currency)) {
                frm.set_value("target_exchange_rate", frm.doc.source_exchange_rate);
                frm.set_value("base_received_amount", frm.doc.base_paid_amount);
            }

            frm.events.set_difference_amount(frm);
        }
    },

    target_exchange_rate: function (frm) {
        frm.set_paid_amount_based_on_received_amount = true;

        if (frm.doc.received_amount) {
            frm.set_value("base_received_amount",
                flt(frm.doc.received_amount) * flt(frm.doc.target_exchange_rate));

            if (!frm.doc.source_exchange_rate &&
                (frm.doc.paid_from_account_currency == frm.doc.paid_to_account_currency)) {
                frm.set_value("source_exchange_rate", frm.doc.target_exchange_rate);
                frm.set_value("base_paid_amount", frm.doc.base_received_amount);
            }

            frm.events.set_difference_amount(frm);
        }
        frm.set_paid_amount_based_on_received_amount = false;
    },

    paid_amount: function (frm) {
        frm.set_value("base_paid_amount", flt(frm.doc.paid_amount) * flt(frm.doc.source_exchange_rate));
        frm.set_value("received_amount", frm.doc.paid_amount);
        frm.trigger("reset_received_amount");

        //Updates remaining amount
        frm.trigger("set_remaining_amount");

        if (frm.doc.payment_type == "Internal Transfer") {
            frm.set_value("third_party_bank_checks_topay", frm.doc.paid_amount);
            frm.set_value("third_party_bank_checks_balance", frm.doc.paid_amount - frm.doc.third_party_bank_checks_acumulated);

            frm.set_value("third_party_documents_topay", frm.doc.paid_amount);
            frm.set_value("third_party_documents_balance", frm.doc.paid_amount - frm.doc.third_party_documents_acumulated);
        }
    },

    received_amount: function (frm) {
        frm.set_paid_amount_based_on_received_amount = true;

        if (!frm.doc.paid_amount && frm.doc.paid_from_account_currency == frm.doc.paid_to_account_currency) {
            frm.set_value("paid_amount", frm.doc.received_amount);

            if (frm.doc.target_exchange_rate) {
                frm.set_value("source_exchange_rate", frm.doc.target_exchange_rate);
            }
            frm.set_value("base_paid_amount", frm.doc.base_received_amount);
        }

        frm.set_value("base_received_amount",
            flt(frm.doc.received_amount) * flt(frm.doc.target_exchange_rate));

        if (frm.doc.payment_type == "Pay")
            frm.events.allocate_party_amount_against_ref_docs(frm, frm.doc.received_amount);
        else
            frm.events.set_difference_amount(frm);

        frm.set_paid_amount_based_on_received_amount = false;
    },

    reset_received_amount: function (frm) {
        if (!frm.set_paid_amount_based_on_received_amount &&
            (frm.doc.paid_from_account_currency == frm.doc.paid_to_account_currency)) {

            frm.set_value("received_amount", frm.doc.paid_amount);

            if (frm.doc.source_exchange_rate) {
                frm.set_value("target_exchange_rate", frm.doc.source_exchange_rate);
            }
            frm.set_value("base_received_amount", frm.doc.base_paid_amount);
        }

        if (frm.doc.payment_type == "Receive")
            frm.events.allocate_party_amount_against_ref_docs(frm, frm.doc.paid_amount);
        else
            frm.events.set_difference_amount(frm);
    },

    get_outstanding_documents: function (frm) {
        frm.clear_table("references");

        if (!frm.doc.party) return;

        frm.events.check_mandatory_to_fetch(frm);
        var company_currency = frappe.get_doc(":Company", frm.doc.company).default_currency;

        return frappe.call({
            method: 'erpnext.accounts.doctype.payment_entry.payment_entry.get_outstanding_reference_documents',
            args: {
                args: {
                    "posting_date": frm.doc.posting_date,
                    "company": frm.doc.company,
                    "party_type": frm.doc.party_type,
                    "payment_type": frm.doc.payment_type,
                    "party": frm.doc.party,
                    "party_account": frm.doc.payment_type == "Receive" ? frm.doc.paid_from : frm.doc.paid_to
                }
            },
            callback: function (r, rt) {
                if (r.message) {
                    var total_positive_outstanding = 0;
                    var total_negative_outstanding = 0;

                    $.each(r.message, function (i, d) {
                        var c = frm.add_child("references");
                        c.reference_doctype = d.voucher_type;
                        c.reference_name = d.voucher_no;
                        c.due_date = d.due_date
                        c.total_amount = d.invoice_amount;
                        c.outstanding_amount = d.outstanding_amount;
                        if (!in_list(["Sales Order", "Purchase Order", "Expense Claim"], d.voucher_type)) {
                            if (flt(d.outstanding_amount) > 0)
                                total_positive_outstanding += flt(d.outstanding_amount);
                            else
                                total_negative_outstanding += Math.abs(flt(d.outstanding_amount));
                        }

                        var party_account_currency = frm.doc.payment_type == "Receive" ?
                            frm.doc.paid_from_account_currency : frm.doc.paid_to_account_currency;

                        if (party_account_currency != company_currency) {
                            c.exchange_rate = d.exchange_rate;
                        } else {
                            c.exchange_rate = 1;
                        }
                        if (in_list(['Sales Invoice', 'Purchase Invoice', "Expense Claim"], d.reference_doctype)) {
                            c.due_date = d.due_date;
                        }
                    });

                    if (
                        (frm.doc.payment_type == "Receive" && frm.doc.party_type == "Customer") ||
                        (frm.doc.payment_type == "Pay" && frm.doc.party_type == "Supplier") ||
                        (frm.doc.payment_type == "Pay" && frm.doc.party_type == "Employee")
                    ) {
                        if (total_positive_outstanding > total_negative_outstanding)
                            frm.set_value("paid_amount",
                                total_positive_outstanding - total_negative_outstanding);
                    } else if (
                        total_negative_outstanding &&
                        total_positive_outstanding < total_negative_outstanding
                    ) {
                        frm.set_value("received_amount",
                            total_negative_outstanding - total_positive_outstanding);
                    }
                }

                frm.events.allocate_party_amount_against_ref_docs(frm,
                    (frm.doc.payment_type == "Receive" ? frm.doc.paid_amount : frm.doc.received_amount));
            }
        });
    },

    allocate_payment_amount: function (frm) {
        if (frm.doc.payment_type == 'Internal Transfer') {
            return
        }

        if (frm.doc.references.length == 0) {
            frm.events.get_outstanding_documents(frm);
        }

        frm.events.allocate_party_amount_against_ref_docs(frm, frm.doc.received_amount);
    },

    allocate_party_amount_against_ref_docs: function (frm, paid_amount) {
        var total_positive_outstanding_including_order = 0;
        var total_negative_outstanding = 0;

        $.each(frm.doc.references || [], function (i, row) {
            if (flt(row.outstanding_amount) > 0)
                total_positive_outstanding_including_order += flt(row.outstanding_amount);
            else
                total_negative_outstanding += Math.abs(flt(row.outstanding_amount));
        })

        var allocated_negative_outstanding = 0;
        if ((frm.doc.payment_type == "Receive" && frm.doc.party_type == "Customer") ||
            (frm.doc.payment_type == "Pay" && frm.doc.party_type == "Supplier") ||
            (frm.doc.payment_type == "Pay" && frm.doc.party_type == "Employee")) {
            if (total_positive_outstanding_including_order > paid_amount) {
                var remaining_outstanding = total_positive_outstanding_including_order - paid_amount;
                allocated_negative_outstanding = total_negative_outstanding < remaining_outstanding ?
                    total_negative_outstanding : remaining_outstanding;
            }

            var allocated_positive_outstanding = paid_amount + allocated_negative_outstanding;
        } else if (in_list(["Customer", "Supplier"], frm.doc.party_type)) {
            if (paid_amount > total_negative_outstanding) {
                if (total_negative_outstanding == 0) {
                    frappe.msgprint(__("Cannot {0} {1} {2} without any negative outstanding invoice",
                        [frm.doc.payment_type,
                            (frm.doc.party_type == "Customer" ? "to" : "from"), frm.doc.party_type]));
                    return false
                } else {
                    frappe.msgprint(__("Paid Amount cannot be greater than total negative outstanding amount {0}", [total_negative_outstanding]));
                    return false;
                }
            } else {
                allocated_positive_outstanding = total_negative_outstanding - paid_amount;
                allocated_negative_outstanding = paid_amount +
                    (total_positive_outstanding_including_order < allocated_positive_outstanding ?
                        total_positive_outstanding_including_order : allocated_positive_outstanding)
            }
        }

        $.each(frm.doc.references || [], function (i, row) {
            row.allocated_amount = 0 //If allocate payment amount checkbox is unchecked, set zero to allocate amount
            if (frm.doc.allocate_payment_amount) {
                if (row.outstanding_amount > 0 && allocated_positive_outstanding > 0) {
                    if (row.outstanding_amount >= allocated_positive_outstanding) {
                        row.allocated_amount = allocated_positive_outstanding;
                    } else {
                        row.allocated_amount = row.outstanding_amount;
                    }

                    allocated_positive_outstanding -= flt(row.allocated_amount);
                } else if (row.outstanding_amount < 0 && allocated_negative_outstanding) {
                    if (Math.abs(row.outstanding_amount) >= allocated_negative_outstanding)
                        row.allocated_amount = -1 * allocated_negative_outstanding;
                    else row.allocated_amount = row.outstanding_amount;

                    allocated_negative_outstanding -= Math.abs(flt(row.allocated_amount));
                }
            }
        })

        frm.refresh_fields()
        frm.events.set_total_allocated_amount(frm);
    },

    set_total_allocated_amount: function (frm) {
        var total_allocated_amount = 0.0;
        var base_total_allocated_amount = 0.0;
        $.each(frm.doc.references || [], function (i, row) {
            if (row.allocated_amount) {
                total_allocated_amount += flt(row.allocated_amount);
                base_total_allocated_amount += flt(flt(row.allocated_amount) * flt(row.exchange_rate),
                    precision("base_paid_amount"));
            }
        });
        frm.set_value("total_allocated_amount", Math.abs(total_allocated_amount));
        frm.set_value("base_total_allocated_amount", Math.abs(base_total_allocated_amount));

        frm.events.set_difference_amount(frm);
    },

    set_difference_amount: function (frm) {
        var unallocated_amount = 0;
        if (frm.doc.party) {
            var party_amount = frm.doc.payment_type == "Receive" ?
                frm.doc.paid_amount : frm.doc.received_amount;

            var total_deductions = frappe.utils.sum($.map(frm.doc.deductions || [],
                function (d) {
                    return flt(d.amount)
                }));

            if (frm.doc.total_allocated_amount < party_amount) {
                if (frm.doc.payment_type == "Receive") {
                    unallocated_amount = party_amount - (frm.doc.total_allocated_amount - total_deductions);
                } else {
                    unallocated_amount = party_amount - (frm.doc.total_allocated_amount + total_deductions);
                }
            }
        }
        frm.set_value("unallocated_amount", unallocated_amount);

        var difference_amount = 0;
        var base_unallocated_amount = flt(frm.doc.unallocated_amount) *
            (frm.doc.payment_type == "Receive" ? frm.doc.source_exchange_rate : frm.doc.target_exchange_rate);

        var base_party_amount = flt(frm.doc.base_total_allocated_amount) + base_unallocated_amount;

        if (frm.doc.payment_type == "Receive") {
            difference_amount = base_party_amount - flt(frm.doc.base_received_amount);
        } else if (frm.doc.payment_type == "Pay") {
            difference_amount = flt(frm.doc.base_paid_amount) - base_party_amount;
        } else {
            difference_amount = flt(frm.doc.base_paid_amount) - flt(frm.doc.base_received_amount);
        }

        $.each(frm.doc.deductions || [], function (i, d) {
            if (d.amount) difference_amount -= flt(d.amount);
        })

        frm.set_value("difference_amount", difference_amount);

        frm.events.hide_unhide_fields(frm);
    },

    check_mandatory_to_fetch: function (frm) {
        $.each(["Company", "Party Type", "Party", "payment_type"], function (i, field) {
            if (!frm.doc[frappe.model.scrub(field)]) {
                frappe.msgprint(__("Please select {0} first", [field]));
                return false;
            }

        });
    },

    validate_reference_document: function (frm, row) {
        var _validate = function (i, row) {
            if (!row.reference_doctype) {
                return;
            }

            if (frm.doc.party_type == "Customer" &&
                !in_list(["Sales Order", "Sales Invoice", "Journal Entry"], row.reference_doctype)
            ) {
                frappe.model.set_value(row.doctype, row.name, "reference_doctype", null);
                frappe.msgprint(__("Row #{0}: Reference Document Type must be one of Sales Order, Sales Invoice or Journal Entry", [row.idx]));
                return false;
            }

            if (frm.doc.party_type == "Supplier" &&
                !in_list(["Purchase Order", "Purchase Invoice", "Journal Entry"], row.reference_doctype)
            ) {
                frappe.model.set_value(row.doctype, row.name, "against_voucher_type", null);
                frappe.msgprint(__("Row #{0}: Reference Document Type must be one of Purchase Order, Purchase Invoice or Journal Entry", [row.idx]));
                return false;
            }

            if (frm.doc.party_type == "Employee" &&
                !in_list(["Expense Claim", "Journal Entry"], row.reference_doctype)
            ) {
                frappe.model.set_value(row.doctype, row.name, "against_voucher_type", null);
                frappe.msgprint(__("Row #{0}: Reference Document Type must be one of Expense Claim or Journal Entry", [row.idx]));
                return false;
            }
        }

        if (row) {
            _validate(0, row);
        } else {
            $.each(frm.doc.vouchers || [], _validate);
        }
    },

    write_off_difference_amount: function (frm) {
        frm.events.set_deductions_entry(frm, "write_off_account");
    },

    set_exchange_gain_loss: function (frm) {
        frm.events.set_deductions_entry(frm, "exchange_gain_loss_account");
    },

    set_deductions_entry: function (frm, account) {
        if (frm.doc.difference_amount) {
            frappe.call({
                method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_company_defaults",
                args: {
                    company: frm.doc.company
                },
                callback: function (r, rt) {
                    if (r.message) {
                        var write_off_row = $.map(frm.doc["deductions"] || [], function (t) {
                            return t.account == r.message[account] ? t : null;
                        });

                        if (!write_off_row.length) {
                            var row = frm.add_child("deductions");
                            row.account = r.message[account];
                            row.cost_center = r.message["cost_center"];
                        } else {
                            var row = write_off_row[0];
                        }

                        row.amount = flt(row.amount) + flt(frm.doc.difference_amount);
                        refresh_field("deductions");

                        frm.events.set_difference_amount(frm);
                    }
                }
            })
        }
    },

    set_remaining_amount: function (frm) {
        var allocated_to_mode_of_payment_amount = 0;
        if (frm.doc.lines) {
            frm.doc.lines.forEach(function (row) {
                if (row.paid_amount) {
                    allocated_to_mode_of_payment_amount += row.paid_amount;
                }
            });
        }
        frm.set_value("allocated_to_mode_of_payment_amount", allocated_to_mode_of_payment_amount);
        if (frm.doc.paid_amount) {
            frm.set_value("remaining_amount", frm.doc.paid_amount - allocated_to_mode_of_payment_amount);
        }


	},

    set_concept: function (frm) {
        if (frm.doc.party && frm.doc.payment_type) {
            if (frm.doc.payment_type == "Receive") {
                frm.set_value("concept", __("Receive from") + " " + __(frm.doc.party_type) + " " + frm.doc.party);
            }
            if (frm.doc.payment_type == "Pay") {
                frm.set_value("concept", __("Pay to") + " " + __(frm.doc.party_type) + " " + frm.doc.party);
            }
        }
        else {
            frm.set_value("concept", "");
        }
    },

    refresh_amounts: function (frm, name, objects) {
        var acumulated = 0;
        if (objects) {
            objects.forEach(function (row) {
                if (row.amount) {
                    acumulated += row.amount;
                }
            });
        }

        frm.refresh_field(name + '_topay');
        var topay = frm.get_field(name + '_topay').value;

        frm.set_value(name + "_acumulated", acumulated);
        frm.set_value(name + "_balance", topay - acumulated);
    },

	on_select_third_party_bank_checks_row: function (frm) {
    	$('div[data-fieldname="third_party_bank_checks"] .grid-row-check').change(function (event) {
			var changed_row = event.target;
			update_selected_third_party_bank_checks(frm, changed_row);
		});
	},

	on_select_third_party_documents_row: function (frm) {
    	$('div[data-fieldname="third_party_documents"] .grid-row-check').change(function (event) {
			var changed_row = event.target;
			update_selected_third_party_documents(frm, changed_row);
		});
	},

    /**
     * Updates concept of documents when the concept of payment entry changes.
     * @param frm
     */
    concept: function (frm) {
        if (frm.doc.concept) {
            if (is_income(frm)) {
                $.each(frm.doc.third_party_documents, function (index, d) {
                    frappe.model.set_value(d.doctype, d.name, "client_detail", frm.doc.concept);
                });
                frm.refresh_field("third_party_documents");
            }
            else {
               $.each(frm.doc.documents, function (index, d) {
                    frappe.model.set_value(d.doctype, d.name, "client_detail", frm.doc.concept);
               });
               frm.refresh_field("documents");
            }
        }

    }
});


frappe.ui.form.on('Payment Entry Reference', {
    reference_doctype: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        frm.events.validate_reference_document(frm, row);
    },

    reference_name: function (frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        return frappe.call({
            method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_reference_details",
            args: {
                reference_doctype: row.reference_doctype,
                reference_name: row.reference_name,
                party_account_currency: frm.doc.payment_type == "Receive" ?
                    frm.doc.paid_from_account_currency : frm.doc.paid_to_account_currency
            },
            callback: function (r, rt) {
                if (r.message) {
                    $.each(r.message, function (field, value) {
                        frappe.model.set_value(cdt, cdn, field, value);
                    })
                    frm.refresh_fields();
                }
            }
        })
    },

    allocated_amount: function (frm) {
        frm.events.set_total_allocated_amount(frm);
    },

    references_remove: function (frm) {
        frm.events.set_total_allocated_amount(frm);
    }
})

frappe.ui.form.on('Payment Entry Deduction', {
    amount: function (frm) {
        frm.events.set_difference_amount(frm);
    },

    deductions_remove: function (frm) {
        frm.events.set_difference_amount(frm);
    }
})

frappe.ui.form.on('Payment Entry Line', {

    lines_add: function (frm, cdt, cdn) {
        var line = locals[cdt][cdn];
        set_up_line(frm, line);
    },
    paid_amount: function (frm, cdt, cdn) {
        var line = locals[cdt][cdn];
        var display = line.paid_amount !== 0;

        frm.events.set_remaining_amount(frm);
        set_up_line(frm, line);

        switch (line.mode_of_payment) {
            case "Cheques propios":
                frm.toggle_display("bank_checks_section", display);
                frm.toggle_display("outgoing_bank_checks", display);

                if(!display) {
                    frm.set_value("outgoing_bank_checks", null);
                } else {
                    row = frm.add_child("outgoing_bank_checks");
                    row.concept = frm.doc.concept;
                    row.company = frm.doc.company;
                }

                frm.set_value("checks_topay", line.paid_amount);

                frm.events.refresh_amounts(frm, "checks", frm.doc.outgoing_bank_checks);
                frm.refresh_fields();
                break;

            case "Documentos propios":
                frm.toggle_display("documents_section", display);
                frm.toggle_display("documents", display);

                if(!display) {
                    frm.set_value("documents", null);
                } else {
                    row = frm.add_child("documents");
                    set_doc_internal_number(row, frm);
                }

                frm.set_value("documents_topay", line.paid_amount);

                frm.events.refresh_amounts(frm, "documents", frm.doc.documents);
                frm.refresh_fields();
                break;

            case "Cheques de Terceros":
                frm.toggle_display("third_party_bank_checks_section", display);
                frm.toggle_display("third_party_bank_checks", display);

                /* cleanup the table */
                if (is_expenditure(frm)) {
                    frm.set_value("third_party_bank_checks", []);
                    frm.set_value("selected_third_party_bank_checks", null);
                    get_third_party_checks(frm);
                } else if(!display){
                    check_counter = 0;
                    frm.set_value("third_party_bank_checks", null);
                } else {
                    row = frm.add_child("third_party_bank_checks");
                    row.concept = frm.doc.concept;
                    row.company = frm.doc.company;
                    set_check_internal_number(row, frm);
                }

			    frm.set_value("third_party_bank_checks_topay", line.paid_amount);
                frm.events.refresh_amounts(frm, "third_party_bank_checks", frm.doc.third_party_bank_checks);
                frm.refresh_fields();
                break;

            case "Documentos de Terceros":
                frm.toggle_display("third_party_documents_section", display);
                frm.toggle_display("third_party_documents", display);

                /* cleanup the table */
                if (is_expenditure(frm)) {
                    frm.set_value("third_party_documents", []);
                    get_third_party_documents(frm);
                }else if(!display){
                    doc_counter = 0;
                    frm.set_value("third_party_documents", null);
                } else {
                    row = frm.add_child("third_party_documents");
                    row.company = frm.doc.company;
                    row.client_detail = frm.doc.concept;
                    set_doc_internal_number(row, frm);
                }

			    frm.set_value("third_party_documents_topay", line.paid_amount);
                frm.events.refresh_amounts(frm, "third_party_documents", frm.doc.third_party_documents);
                frm.refresh_fields();
                break;

            default:
                break;
        }

        if (line.mode_of_payment == "Cheques propios" || line.mode_of_payment == "Cheques de Terceros") {
            // show average day if payment type is Cheques propios or Cheques de Terceros
            frm.toggle_display("bank_checks_average_days_section", is_expenditure(frm)
                && (line.paid_amount != 0 || !is_empty_selected_third_party_bank_checks(frm) || !is_empty_outgoing_bank_checks(frm)));

            update_bank_checks_average_days(frm);
        }



    },

    mode_of_payment: function (frm, cdt, cdn) {
        var line = locals[cdt][cdn];
        set_mode_of_payment_account(frm, line);
    },


});

/**
 * @description Bank Checks events handler
 */
frappe.ui.form.on('Payment Entry Bank Check', {
    outgoing_bank_checks_add: function (frm, cdt, cdn) {
        check = locals[cdt][cdn];
        check.concept = frm.doc.concept;
        check.company = frm.doc.company;
        frm.refresh_fields();
    },
    outgoing_bank_checks_remove: function (frm) {
        frm.events.refresh_amounts(frm, "checks", frm.doc.outgoing_bank_checks);
        update_bank_checks_average_days(frm);
    },
    third_party_bank_checks_add: function (frm, cdt, cdn) {
        check = locals[cdt][cdn];
		check.company = frm.doc.company;
        check.concept = frm.doc.concept;
		if (is_income(frm)) {
            set_check_internal_number(check, frm);
        }
    },
    amount: function (frm, cdt, cdn) {


		if(is_expenditure(frm)) {
            frm.events.refresh_amounts(frm, "checks", frm.doc.outgoing_bank_checks);
		    update_bank_checks_average_days(frm);
		}
		else {
		    frm.events.refresh_amounts(frm, "third_party_bank_checks", frm.doc.third_party_bank_checks);
        }
    },

    payment_date: function (frm, cdt, cdn) {
        check = locals [cdt][cdn];
        if (is_expenditure(frm)) {
            if (frappe.datetime.get_diff(frm.doc.posting_date, check.payment_date) > 0) {
                frappe.throw(__("Payment Date of Bank Check must be greater than Posting Date"));
                check.payment_date = frm.doc.posting_date;
                frm.refresh_fields();
            }
            update_bank_checks_average_days(frm);
        }
    }
})

/**
 * @description Documents events handler
 */
frappe.ui.form.on('Payment Entry Document', {
    documents_remove: function (frm) {
        frm.events.refresh_amounts(frm, "documents", frm.doc.documents);
    },
    documents_add: function (frm, cdt, cdn) {
        doc = locals[cdt][cdn];
        set_doc_internal_number(doc, frm);
    },
    third_party_documents_add: function (frm, cdt, cdn) {
        row = locals[cdt][cdn];
		row.company = frm.doc.company;
		if (is_income(frm)) {
            set_doc_internal_number(row, frm);
            row.client_detail = frm.doc.concept;
        }
    },
    amount: function (frm) {
        frm.events.refresh_amounts(frm, "third_party_documents", frm.doc.third_party_documents);

		if(is_expenditure(frm)) {
		    frm.events.refresh_amounts(frm, "documents", frm.doc.documents);
		}
    }
})

//Initializes pai_from and paid_to fields
var set_up_line = function (frm, line) {
    if (frm.doc.payment_type == "Miscellaneous Income" || frm.doc.payment_type == "Miscellaneous Expenditure" || !frm.doc.party) {
        frappe.call({
            method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_company_defaults",
            args: {
                company: frm.doc.company
            },
            callback: function (r, rt) {
                if (r.message) {
                    if (is_income(frm)) {
                        line['paid_from'] = r.message.default_receivable_account;
                    }
                    else {
                        line['paid_to'] = r.message.default_payable_account;
                    }
                }
            }
        });
    }
    //get default account for specific party
    else {
        frappe.call({
            method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_party_details",
            args: {
                company: frm.doc.company,
                party_type: frm.doc.party_type,
                party: frm.doc.party,
                date: frm.doc.posting_date
            },
            callback: function (r, rt) {
                if (r.message) {
                    if (frm.doc.payment_type == "Receive") {
                        line['paid_from'] = r.message.party_account;
                    }
                    else {
                        line['paid_to'] = r.message.party_account;
                    }
                }
            }
        });
    }

    set_mode_of_payment_account(frm, line);

    frm.refresh_field("lines");

};

var set_mode_of_payment_account = function (frm, line) {
    if (line['mode_of_payment']) {
        get_payment_mode_account(frm, line['mode_of_payment'], function (account) {

            var payment_account_field;
            if (is_income(frm)) {
                payment_account_field = "paid_to";
            }
            else {
                payment_account_field = "paid_from";
            }
            line [payment_account_field] = account;
            frm.refresh_field("lines");
        });
    }
};

var set_up_payment_lines = function (frm) {
    if (!frm.doc.lines || frm.doc.lines.length === 0) {
        /**Fill Payment Lines with All Modes Of Payment */
        frappe.call({
            method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_mod_of_payments",
            args: {
                company: frm.doc.company,
				payment_type: is_income(frm) ? "income": "expenditure"
            },
            callback: function (r) {
                if (r.message) {
                    $.each(r.message, function (index, value) {
                        var child = frm.add_child("lines");
                        child.mode_of_payment = value.name;
                        child.paid_amount = 0
                    });
                    var df1 = frappe.meta.get_docfield("Payment Entry Line","mode_of_payment", frm.doc.name);
                    df1.read_only = 1;
                    frm.refresh_field("lines");

                }
            }
        });
    }
}

/**
 * @description Gets the last internal number registered on the database and sets the given object internal number.
 * @param obj to set the internal number
 */
var set_check_internal_number = function (obj, frm) {
    frappe.call({
        method: "erpnext.accounts.doctype.bank_check.bank_check.get_last_internal_number",
        args: {},
        callback: function (r) {
            check_counter++;
            obj.internal_number = parseInt(r.message[0]) + check_counter;

            frm.refresh_field("third_party_bank_checks");
        }
    });
}

/**
 * @description Gets the last internal number registered on the database and sets the given object internal number.
 * @param obj to set the internal number
 */
var set_doc_internal_number = function (obj, frm) {
    frappe.call({
        method: "erpnext.accounts.doctype.document.document.get_last_internal_number",
        args: {},
        callback: function (r) {
            doc_counter++;
            obj.internal_number = parseInt(r.message[0]) + doc_counter;

            frm.refresh_field("documents");
            frm.refresh_field("third_party_documents");
        }
    });
}

/**
 * @description Returns if the payment entry is an income or not.
 * @returns {boolean}
 */
var is_income = function (frm) {
    return (frm.doc.payment_type == "Receive" || frm.doc.payment_type == "Miscellaneous Income");
}

var is_expenditure = function (frm) {
	return (frm.doc.payment_type == "Pay" || frm.doc.payment_type == "Miscellaneous Expenditure");
}


/** CHECK WALLET IMPLEMENTATION **/

/**
 * @description get all third party checks that are unused
 * @param frm
 */
var get_third_party_checks = function (frm) {
	frappe.call({
		method: "erpnext.accounts.doctype.bank_check.bank_check.get_unused_third_party_checks",
		args: {
			"company": frm.doc.company,
		},
		callback: function (r) {
			if (!r.message) {
		        frappe.msgprint(__("There are no third-party checks in the wallet"));
            }
		    $.each(r.message, function (index, check) {
				var row = frm.add_child("third_party_bank_checks");
				row.bank = check.bank;
				row.number = check.number;
				row.internal_number = check.internal_number;
				row.payment_date = check.payment_date;
				row.amount = check.amount;
            });
			frm.refresh_fields();
			frm.events.on_select_third_party_bank_checks_row(frm);
        }
	});
}

var update_selected_third_party_bank_checks = function (frm, changed_row) {

	//calculate number of row checked to retrieve the element
	var row_index = $(changed_row).next().text();
	if(!isNaN(parseInt(row_index))) {
        var bank_checks = $(frm.doc.third_party_bank_checks).filter(function (i, element) {
            return element.idx == row_index;
        });

        changed_bank_check = bank_checks[0];

        //Check was selected
        if ($(changed_row).is(':checked')) {
            add_selected_bank_check(frm, changed_bank_check);
        }
        // Removes check from selected check list
        else {
            remove_bank_check(frm, changed_bank_check);
        }
    }
    else {
	    frm.set_value("selected_third_party_bank_checks", null);

	    if ($(changed_row).is(':checked')) {
	        $.each(frm.doc.third_party_bank_checks, function (index, check) {
	            add_selected_bank_check(frm, check);
            });
        }
        frm.refresh_field("selected_third_party_bank_checks");
    }
    frm.events.refresh_amounts(frm, "third_party_bank_checks", frm.doc.selected_third_party_bank_checks);
	update_bank_checks_average_days(frm);
}

var add_selected_bank_check = function (frm, changed_bank_check) {
  var child = frm.add_child("selected_third_party_bank_checks");
    child.amount = changed_bank_check.amount;
    child.internal_number = changed_bank_check.internal_number;
    child.payment_date = changed_bank_check.payment_date;
    child.idx = changed_bank_check.idx;

}

/**
 * Find changed_bank_check in selected_third_party_bank_checks and deletes it.
 * the equality is given by idx of a check
 * @param frm
 * @param changed_bank_check
 */
var remove_bank_check = function (frm, changed_bank_check) {
	var delete_index;
	// find the index of the check that must be removed
	$.each(frm.doc.selected_third_party_bank_checks, function (pos, check) {
		if (check.idx == changed_bank_check.idx) {
			delete_index = pos;
		}
    });

	frm.doc.selected_third_party_bank_checks.splice(delete_index, 1);

	frm.refresh_field("selected_third_party_bank_checks");
}


/** DOCUMENTS WALLET IMPLEMENTATION **/

/**
 * @description get all third party documents that are unused
 * @param frm
 */
var get_third_party_documents = function (frm) {
	frappe.call({
		method: "erpnext.accounts.doctype.document.document.get_unused_third_party_documents",
		args: {
			"company": frm.doc.company,
		},
		callback: function (r) {
		    if (!r.message) {
		        frappe.msgprint(__("There are no third-party documents in the wallet"));
            }
			$.each(r.message, function (index, doc) {
				var row = frm.add_child("third_party_documents");
				row.date = doc.date;
				row.client_detail = doc.client_detail;
				row.internal_number = doc.internal_number;
				row.amount = doc.amount;
            });
            frm.refresh_fields();
			frm.events.on_select_third_party_documents_row(frm);
        }
	});
}

var update_selected_third_party_documents = function (frm, changed_row) {

	//calculate number of row checked to retrieve the element
	var row_index = $(changed_row).next().text();

	if(!isNaN(parseInt(row_index))) {
        var changed_document = $(frm.doc.third_party_documents).filter(function (i, element) {
            return element.idx == row_index;
        })[0];


        if ( $(changed_row).is(':checked') ) {
            add_selected_document(frm, changed_document);
        }
        else {
            remove_document(frm, changed_document);
        }
    }
    else {
	    frm.set_value("selected_third_party_documents", null);
        if ( $(changed_row).is(':checked') ) {
            $.each(frm.doc.third_party_documents, function (index, d) {
                add_selected_document(frm, d);
            });
        }
	}
	frm.events.refresh_amounts(frm, "third_party_documents", frm.doc.selected_third_party_documents);

}

var add_selected_document = function (frm, changed_document) {
   var child = frm.add_child("selected_third_party_documents");
    child.amount = changed_document.amount;
    child.internal_number = changed_document.internal_number;
    child.date = changed_document.date;
    child.client_detail = changed_document.client_detail;
    child.idx = changed_document.idx;
}

/**
 * Find changed_document in selected_third_party_documents and deletes it.
 * the equality is given by idx of a document
 * @param frm
 * @param changed_document
 */
var remove_document = function (frm, changed_document) {
	var delete_index;
	// find the index of the check that must be removed
	$.each(frm.doc.selected_third_party_documents, function (pos, doc) {
		if (doc.idx !== undefined && doc.idx == changed_document.idx) {
			delete_index = pos;
		}
    });

	frm.doc.selected_third_party_documents.splice(delete_index, 1);

	frm.refresh_field("selected_third_party_documents");
}


/**
 * Shows selected third party checks when payment is closed
 * @param frm
 */
var show_selected_third_party_checks = function (frm) {

    frm.set_df_property("third_party_bank_checks_section", "hidden", false);
    frm.set_df_property("third_party_bank_checks", "hidden", true);
    frm.set_df_property("selected_third_party_bank_checks", "hidden", false);
}


/**
 * Show selected third party documents when payment is closed
 * @param frm
 */
var show_selected_third_party_documents = function (frm) {
    frm.set_df_property("third_party_documents_section", "hidden", false);
    frm.set_df_property("third_party_documents", "hidden", true);
    frm.set_df_property("selected_third_party_documents", "hidden", false);
}

var show_new_third_party_checks = function (frm) {
    frm.set_df_property("third_party_bank_checks_section", "hidden", false);
    frm.set_df_property("third_party_bank_checks", "hidden", false);
    //frm.set_df_property("third_party_checks_amounts_section", "hidden", true);
    frm.set_df_property("selected_third_party_bank_checks", "hidden", true);
}

var show_new_third_party_documents =  function (frm) {
    frm.set_df_property("third_party_documents_section", "hidden", false);
    frm.set_df_property("third_party_documents", "hidden", false);
    //frm.set_df_property("third_party_documents_amounts_section", "hidden", true);
    frm.set_df_property("selected_third_party_documents", "hidden", true);

}

/**
 * clear table and hides section that contains it
 * @param frm
 * @param table_name
 */
var clear_table = function (frm, table_name) {
    frm.set_value(table_name, null);
    frm.toggle_display(table_name + "_section", false);

    // clear selected items
    frm.set_value("selected_" + table_name, null);

    // clear amounts
    frm.set_value(table_name + "_acumulated", 0);
    frm.set_value(table_name + "_balance", frm.get_field(table_name + "_topay").value);

}


var get_company_currency = function (frm) {
    return frm.doc.company ? frappe.get_doc(":Company", frm.doc.company).default_currency : "";
}

/**
 * Filter Company type
 */
frappe.ui.form.on("Payment Entry", "refresh", function(frm) {
    cur_frm.set_query("company", function () {
        var types = ["A"];
        if(frappe.user_roles.includes("Global Vision")){
            types.push("B", "A+B");
        }
        return {
            "doctype": "Company",
            "filters": {
                "type": ["in", types]
            }
        }
    });
});


var update_bank_checks_average_days = function (frm) {
    total_amount = 0;
    days_per_amount = 0;
    $.each(frm.doc.selected_third_party_bank_checks, function (index, check) {
        if (check.payment_date && check.amount && frm.doc.posting_date) {
            total_amount += check.amount;
            day_diff = frappe.datetime.get_day_diff(check.payment_date, frm.doc.posting_date);
            days_per_amount += (check.amount * day_diff);
        }
    });

    $.each(frm.doc.outgoing_bank_checks, function (index, check) {
        if (check.payment_date && check.amount && frm.doc.posting_date) {
            total_amount += check.amount;
            day_diff = frappe.datetime.get_day_diff(check.payment_date, frm.doc.posting_date);
            days_per_amount += (check.amount * day_diff);
        }
    });

    if (total_amount != 0) {
        frm.set_value("bank_checks_average_days", days_per_amount / total_amount);
    }
    else {
        frm.set_value("bank_checks_average_days", 0);
    }

}

var is_empty_selected_third_party_bank_checks = function (frm) {
    return (!frm.doc.selected_third_party_checks || frm.doc.selected_third_party_checks.length == 0);
}

var is_empty_outgoing_bank_checks = function (frm) {
    return (!frm.doc.outgoing_bank_checks || frm.doc.outgoing_bank_checks.length == 0);
}


var set_up_internal_transfer = function (frm) {
    frappe.call({
        method: "erpnext.accounts.doctype.payment_entry.payment_entry.get_account_details",
        args: {
            "account": frm.doc.paid_from,
            "date": frm.doc.posting_date
        },
        callback: function (r, rt) {
            if (r.message["account_type"] == "Check Wallet") {
                frm.set_value("third_party_bank_checks_topay", frm.doc.paid_amount);
                get_third_party_checks(frm);
                show_third_party_bank_checks(frm);
            }
            if (r.message["account_type"] == "Document Wallet") {
                frm.set_value("third_party_documents_topay", frm.doc.paid_amount);
                get_third_party_documents(frm);
                show_third_party_documents(frm);
            }
        }

    });

}

var show_third_party_bank_checks = function (frm) {
    frm.toggle_display("third_party_bank_checks_section", true);
    frm.toggle_display("third_party_bank_checks", true);
    frm.set_df_property("third_party_bank_checks", "read_only", true);
}

var show_third_party_documents = function (frm) {
    frm.toggle_display("third_party_documents_section", true);
    frm.toggle_display("third_party_documents", true);
    frm.set_df_property("third_party_documents", "read_only", true);
}