# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe import _, scrub, ValidationError
from frappe.utils import flt, comma_or, nowdate
from erpnext.accounts.utils import get_outstanding_invoices, get_account_currency, get_balance_on, \
    get_last_daily_movement_balance
from erpnext.accounts.party import get_party_account
from erpnext.accounts.doctype.journal_entry.journal_entry \
    import get_average_exchange_rate, get_default_bank_cash_account
from erpnext.setup.utils import get_exchange_rate
from erpnext.accounts.general_ledger import make_gl_entries
from erpnext.hr.doctype.expense_claim.expense_claim import update_reimbursed_amount
from erpnext.controllers.accounts_controller import AccountsController


class InvalidPaymentEntry(ValidationError): pass


class PaymentEntry(AccountsController):
    def setup_party_account_field(self):
        self.party_account_field = None
        self.party_account = None
        self.party_account_currency = None

        if self.payment_type == "Receive":
            self.party_account_field = "paid_from"
            self.party_account = self.paid_from
            self.party_account_currency = self.paid_from_account_currency

        elif self.payment_type == "Pay":
            self.party_account_field = "paid_to"
            self.party_account = self.paid_to
            self.party_account_currency = self.paid_to_account_currency

        elif self.payment_type == "Miscellaneous Income":
            self.party_account = get_company_defaults(self.company).default_receivable_account
        elif self.payment_type == "Miscellaneous Expenditure":
            self.party_account = get_company_defaults(self.company).default_payable_account

    def validate(self):
        self.setup_party_account_field()
        self.set_missing_values()
        self.validate_payment_type()
        self.validate_party_details()

        self.validate_bank_accounts()
        self.set_exchange_rate()
        self.validate_mandatory()
        self.validate_reference_documents()
        self.set_amounts()
        self.clear_unallocated_reference_document_rows()
        self.validate_payment_against_negative_invoice()

        self.set_title()
        self.set_remarks()
        self.validate_duplicate_entry()
        self.validate_allocated_amount()

        self.set_concept()
        self.validate_payment_lines()
        self.validate_bank_checks()
        self.validate_documents()

        if self.payment_type == "Internal Transfer":
            self.validate_internal_transfer()

        #Removes 'Draft' transition, submit document directly
        self._action = "submit"
        self.docstatus = 1


    def on_submit(self):
        self.setup_party_account_field()

        if self.difference_amount:
            frappe.throw(_("Difference Amount must be zero"))
        self.make_gl_entries()
        self.update_advance_paid()
        self.update_expense_claim()

        self.update_selected_third_party_bank_checks()
        self.update_selected_third_party_documents()

        self.save_outgoing_bank_checks()
        self.save_new_third_party_bank_checks()
        self.save_documents()

    def on_cancel(self):
        self.setup_party_account_field()
        self.make_gl_entries(cancel=1)
        self.update_advance_paid()
        self.update_expense_claim()
        self.delink_advance_entry_references()

    def validate_duplicate_entry(self):
        reference_names = []
        for d in self.get("references"):
            if (d.reference_doctype, d.reference_name) in reference_names:
                frappe.throw(_("Row #{0}: Duplicate entry in References {1} {2}").format(d.idx, d.reference_doctype,
                                                                                         d.reference_name))
            reference_names.append((d.reference_doctype, d.reference_name))

    def validate_allocated_amount(self):
        for d in self.get("references"):
            if (flt(d.allocated_amount)) > 0:
                if flt(d.allocated_amount) > flt(d.outstanding_amount):
                    frappe.throw(
                        _("Row #{0}: Allocated Amount cannot be greater than outstanding amount.").format(d.idx))

    def delink_advance_entry_references(self):
        for reference in self.references:
            if reference.reference_doctype in ("Sales Invoice", "Purchase Invoice"):
                doc = frappe.get_doc(reference.reference_doctype, reference.reference_name)
                doc.delink_advance_entries(self.name)

    def set_missing_values(self):
        if self.payment_type == "Internal Transfer":
            for field in ("party", "party_balance", "total_allocated_amount",
                          "base_total_allocated_amount", "unallocated_amount"):
                self.set(field, None)
            self.references = []

        elif self.payment_type in ("Miscellaneous Income", "Miscellaneous Expenditure"):
            self.party = None
            self.party_balance = None

        else:
            if not self.party_type:
                frappe.throw(_("Party Type is mandatory"))

            if not self.party:
                frappe.throw(_("Party is mandatory"))

            self.party_name = frappe.db.get_value(self.party_type, self.party,
                                                  self.party_type.lower() + "_name")

        if self.party:
            if not self.party_balance:
                self.party_balance = get_balance_on(party_type=self.party_type,
                                                    party=self.party, date=self.posting_date, company=self.company)

            if not self.party_account:
                party_account = get_party_account(self.party_type, self.party, self.company)
                self.set(self.party_account_field, party_account)
                self.party_account = party_account

        if self.paid_from and not (self.paid_from_account_currency or self.paid_from_account_balance):
            acc = get_account_details(self.paid_from, self.posting_date)
            self.paid_from_account_currency = acc.account_currency
            self.paid_from_account_balance = acc.account_balance

        if self.paid_to and not (self.paid_to_account_currency or self.paid_to_account_balance):
            acc = get_account_details(self.paid_to, self.posting_date)
            self.paid_to_account_currency = acc.account_currency
            self.paid_to_account_balance = acc.account_balance

        self.party_account_currency = self.paid_from_account_currency \
            if self.payment_type == "Receive" else self.paid_to_account_currency

        self.set_missing_ref_details()

    def set_missing_ref_details(self):
        for d in self.get("references"):
            if d.allocated_amount:
                ref_details = get_reference_details(d.reference_doctype,
                                                    d.reference_name, self.party_account_currency)

                for field, value in ref_details.items():
                    if not d.get(field):
                        d.set(field, value)

    def validate_payment_type(self):
        if self.payment_type not in ("Receive", "Pay", "Internal Transfer", "Miscellaneous Income",
                                     "Miscellaneous Expenditure"):
            frappe.throw(_("Payment Type must be one of Receive, Pay and Internal Transfer"))

    def validate_party_details(self):
        if self.party:
            if not frappe.db.exists(self.party_type, self.party):
                frappe.throw(_("Invalid {0}: {1}").format(self.party_type, self.party))

            if self.party_account:
                party_account_type = "Receivable" if self.party_type == "Customer" else "Payable"
                self.validate_account_type(self.party_account, [party_account_type])

    # Accounts are required only in Internal Transfer
    def validate_bank_accounts(self):
        if self.payment_type == "Internal Transfer":
            self.validate_account_type(self.paid_from, ["Bank", "Cash", "Check Wallet", "Document Wallet"])
            self.validate_account_type(self.paid_to, ["Bank", "Cash"])

    def validate_account_type(self, account, account_types):
        account_type = frappe.db.get_value("Account", account, "account_type")
        if account_type not in account_types:
            frappe.throw(_("Account Type for {0} must be {1}").format(account, comma_or(account_types)))

    def set_exchange_rate(self):
        if self.paid_from and not self.source_exchange_rate:
            if self.paid_from_account_currency == self.company_currency:
                self.source_exchange_rate = 1
            else:
                self.source_exchange_rate = get_exchange_rate(self.paid_from_account_currency,
                                                              self.company_currency, self.posting_date)

        if self.paid_to and not self.target_exchange_rate:
            self.target_exchange_rate = get_exchange_rate(self.paid_to_account_currency,
                                                          self.company_currency, self.posting_date)

    def validate_mandatory(self):
        # received_amount, source_exchange_rate and target_exchange_rate are not mandatory
        if not self.get("paid_amount"):
            frappe.throw(_("{0} is mandatory").format(self.meta.get_label("paid_amount")))

    def validate_reference_documents(self):
        if self.party_type == "Customer":
            valid_reference_doctypes = ("Sales Order", "Sales Invoice", "Journal Entry")
        elif self.party_type == "Supplier":
            valid_reference_doctypes = ("Purchase Order", "Purchase Invoice", "Journal Entry", "Operation Completion")
        elif self.party_type == "Employee":
            valid_reference_doctypes = ("Expense Claim", "Journal Entry")


        elif self.payment_type == "Miscellaneous Expenditure":
            valid_reference_doctypes = ("Eventual Purchase Invoice")

        for d in self.get("references"):
            if not d.allocated_amount:
                continue
            if d.reference_doctype not in valid_reference_doctypes:
                frappe.throw(_("Reference Doctype must be one of {0}")
                             .format(comma_or(valid_reference_doctypes)))

            elif d.reference_name:
                if not frappe.db.exists(d.reference_doctype, d.reference_name):
                    frappe.throw(_("{0} {1} does not exist").format(d.reference_doctype, d.reference_name))
                else:
                    ref_doc = frappe.get_doc(d.reference_doctype, d.reference_name)

                    if d.reference_doctype not in ["Journal Entry", "Eventual Purchase Invoice", "Operation Completion"]:
                        if self.party != ref_doc.get(scrub(self.party_type)):
                            frappe.throw(_("{0} {1} does not associated with {2} {3}")
                                         .format(d.reference_doctype, d.reference_name, self.party_type, self.party))

                    elif d.reference_doctype == "Journal Entry":
                        self.validate_journal_entry()

                    if d.reference_doctype in ("Sales Invoice", "Purchase Invoice", "Expense Claim"):
                        if self.party_type == "Customer":
                            ref_party_account = ref_doc.debit_to
                        elif self.party_type == "Supplier":
                            ref_party_account = ref_doc.credit_to
                        elif self.party_type == "Employee":
                            ref_party_account = ref_doc.payable_account

                        if ref_party_account != self.party_account:
                            frappe.throw(_("{0} {1} is associated with {2}, but Party Account is {3}")
                                         .format(d.reference_doctype, d.reference_name, ref_party_account,
                                                 self.party_account))

                    if ref_doc.docstatus != 1:
                        frappe.throw(_("{0} {1} must be submitted")
                                     .format(d.reference_doctype, d.reference_name))

    def validate_journal_entry(self):
        for d in self.get("references"):
            if d.allocated_amount and d.reference_doctype == "Journal Entry":
                je_accounts = frappe.db.sql("""select debit, credit from `tabJournal Entry Account`
                        where account = %s and party=%s and docstatus = 1 and parent = %s
                        and (reference_type is null or reference_type in ("", "Sales Order", "Purchase Order"))
                        """, (self.party_account, self.party, d.reference_name), as_dict=True)

                if not je_accounts:
                    frappe.throw(_(
                        "Row #{0}: Journal Entry {1} does not have account {2} or already matched against another voucher")
                                 .format(d.idx, d.reference_name, self.party_account))
                else:
                    dr_or_cr = "debit" if self.payment_type == "Receive" else "credit"
                    valid = False
                    for jvd in je_accounts:
                        if flt(jvd[dr_or_cr]) > 0:
                            valid = True
                    if not valid:
                        frappe.throw(_("Against Journal Entry {0} does not have any unmatched {1} entry")
                                     .format(d.reference_name, dr_or_cr))

    def set_amounts(self):
        self.set_amounts_in_company_currency()
        self.set_total_allocated_amount()
        self.set_unallocated_amount()
        self.set_difference_amount()

    def set_amounts_in_company_currency(self):
        self.base_paid_amount, self.base_received_amount, self.difference_amount = 0, 0, 0
        if self.paid_amount:
            self.base_paid_amount = flt(flt(self.paid_amount) * flt(self.source_exchange_rate),
                                        self.precision("base_paid_amount"))

        # Bazz received amount is always equal to paid amount
        self.received_amount = self.paid_amount

        if self.received_amount:
            self.base_received_amount = flt(flt(self.received_amount) * flt(self.target_exchange_rate),
                                            self.precision("base_received_amount"))

    def set_total_allocated_amount(self):
        if self.payment_type == "Internal Transfer":
            return

        total_allocated_amount, base_total_allocated_amount = 0, 0
        for d in self.get("references"):
            if d.allocated_amount:
                total_allocated_amount += flt(d.allocated_amount)
                base_total_allocated_amount += flt(flt(d.allocated_amount) * flt(d.exchange_rate),
                                                   self.precision("base_paid_amount"))

        self.total_allocated_amount = abs(total_allocated_amount)
        self.base_total_allocated_amount = abs(base_total_allocated_amount)

    def set_unallocated_amount(self):
        self.unallocated_amount = 0
        if self.party or self.get("references"):
            party_amount = self.paid_amount

            total_deductions = sum([flt(d.amount) for d in self.get("deductions")])

            if self.total_allocated_amount < party_amount:
                if self.payment_type == "Receive":
                    self.unallocated_amount = party_amount - (self.total_allocated_amount - total_deductions)
                else:
                    self.unallocated_amount = party_amount - (self.total_allocated_amount + total_deductions)
        else:
            self.unallocated_amount = self.paid_amount

    def set_difference_amount(self):
        base_unallocated_amount = flt(self.unallocated_amount) * (flt(self.source_exchange_rate)
                                                                  if self.payment_type == "Receive" else flt(
            self.target_exchange_rate))

        base_party_amount = flt(self.base_total_allocated_amount) + flt(base_unallocated_amount)

        if self.payment_type == "Receive":
            self.difference_amount = base_party_amount - self.base_received_amount
        elif self.payment_type == "Pay":
            self.difference_amount = self.base_paid_amount - base_party_amount
        else:
            self.difference_amount = self.base_paid_amount - flt(self.base_received_amount)

        for d in self.get("deductions"):
            if d.amount:
                self.difference_amount -= flt(d.amount)

        self.difference_amount = flt(self.difference_amount, self.precision("difference_amount"))

    def clear_unallocated_reference_document_rows(self):
        self.set("references", self.get("references", {"allocated_amount": ["not in", [0, None, ""]]}))

        frappe.db.sql("""delete from `tabPayment Entry Reference`
              where parent = %s and allocated_amount = 0""", self.name)

    def validate_payment_against_negative_invoice(self):
        if ((self.payment_type == "Pay" and self.party_type == "Customer")
            or (self.payment_type == "Receive" and self.party_type == "Supplier")):

            total_negative_outstanding = sum([abs(flt(d.outstanding_amount))
                                              for d in self.get("references") if flt(d.outstanding_amount) < 0])

            party_amount = self.paid_amount if self.payment_type == "Receive" else self.received_amount

            if not total_negative_outstanding:
                frappe.throw(_("Cannot {0} {1} {2} without any negative outstanding invoice")
                             .format(self.payment_type, ("to" if self.party_type == "Customer" else "from"),
                                     self.party_type), InvalidPaymentEntry)

            elif party_amount > total_negative_outstanding:
                frappe.throw(_("Paid Amount cannot be greater than total negative outstanding amount {0}")
                             .format(total_negative_outstanding), InvalidPaymentEntry)

    def set_title(self):
        if self.payment_type in ("Receive", "Pay"):
            self.title = self.party

        elif self.payment_type in ("Miscellaneous Income", "Miscellaneous Expenditure"):
            self.title = _(self.payment_type) + "  " + self.posting_date
        else:
            self.title = self.paid_from + " " + self.paid_to

    def set_remarks(self):
        if self.remarks: return

        if self.payment_type == "Internal Transfer":
            remarks = [_("Amount {0} {1} transferred from {2} to {3}")
                           .format(self.paid_from_account_currency, self.paid_amount, self.paid_from, self.paid_to)]
        else:

            remarks = [_("Amount {0} {1} {2} {3} {4}").format(
                self.party_account_currency,
                self.paid_amount if self.payment_type == "Receive" else self.received_amount,
                _("received from") if self.payment_type == "Receive" else _("paid to"), _(self.party_type), self.party
            )]

        if self.reference_no:
            remarks.append(_("Transaction reference no {0} dated {1}")
                           .format(self.reference_no, self.reference_date))

        if self.payment_type in ["Receive", "Pay"]:
            for d in self.get("references"):
                if d.allocated_amount:
                    remarks.append(_("Amount {0} {1} against {2} {3}").format(self.party_account_currency,
                                                                              d.allocated_amount, d.reference_doctype,
                                                                              d.reference_name))

        for d in self.get("deductions"):
            if d.amount:
                remarks.append(_("Amount {0} {1} deducted against {2}")
                               .format(self.company_currency, d.amount, d.account))

        self.set("remarks", "\n".join(remarks))

    def make_gl_entries(self, cancel=0, adv_adj=0):
        if self.payment_type in ("Receive", "Pay") and not self.get("party_account_field"):
            self.setup_party_account_field()

        gl_entries = []

        self.add_internal_transfer_bank_gl_entries(gl_entries)

       # self.add_lines_party_gl_entries(gl_entries)

        self.add_party_gl_entries(gl_entries)
        self.add_lines_bank_gl_entries(gl_entries)
        self.generate_gl_entries_for_bank_checks(gl_entries)

        self.add_deductions_gl_entries(gl_entries)

        make_gl_entries(gl_entries, cancel=cancel, adv_adj=adv_adj)

    def add_party_gl_entries(self, gl_entries):
        if self.party_account:
            if self.payment_type == "Receive":
                against_account = self.paid_to
            else:
                against_account = self.paid_from

            party_gl_dict = self.get_gl_dict({
                "account": self.party_account,
                "party_type": self.party_type,
                "party": self.party,
                "against": against_account,
                "account_currency": self.party_account_currency
            })

            dr_or_cr = "credit" if (self.payment_type == "Receive" or self.payment_type == "Miscellaneous Income") else "debit"

            for d in self.get("references"):

                gle = party_gl_dict.copy()
                gle.update({
                    "against_voucher_type": d.reference_doctype,
                    "against_voucher": d.reference_name
                })

                allocated_amount_in_company_currency = flt(flt(d.allocated_amount) * flt(d.exchange_rate),
                                                           self.precision("paid_amount"))

                gle.update({
                    dr_or_cr + "_in_account_currency": d.allocated_amount,
                    dr_or_cr: allocated_amount_in_company_currency
                })

                gl_entries.append(gle)


            if self.unallocated_amount:
                base_unallocated_amount = base_unallocated_amount = self.unallocated_amount * \
                                                                    (
                                                                        self.source_exchange_rate if self.payment_type == "Receive" else self.target_exchange_rate)

                gle = party_gl_dict.copy()

                gle.update({
                    dr_or_cr + "_in_account_currency": self.unallocated_amount,
                    dr_or_cr: base_unallocated_amount
                })

                gl_entries.append(gle)


    def add_internal_transfer_bank_gl_entries(self, gl_entries):
        if self.payment_type == "Internal Transfer":
            gl_entries.append(
                self.get_gl_dict({
                    "account": self.paid_from,
                    "account_currency": self.paid_from_account_currency,
                    "against": self.party if self.payment_type == "Pay" else self.paid_to,
                    "credit_in_account_currency": self.paid_amount,
                    "credit": self.base_paid_amount,
                    "concept": self.concept
                })
            )
            gl_entries.append(
                self.get_gl_dict({
                    "account": self.paid_to,
                    "account_currency": self.paid_to_account_currency,
                    "against": self.party if self.payment_type == "Receive" else self.paid_from,
                    "debit_in_account_currency": self.received_amount,
                    "debit": self.base_received_amount,
                    "concept": self.concept
                })
            )

    def add_deductions_gl_entries(self, gl_entries):
        for d in self.get("deductions"):
            if d.amount:
                account_currency = get_account_currency(d.account)
                if account_currency != self.company_currency:
                    frappe.throw(_("Currency for {0} must be {1}").format(d.account, self.company_currency))

                gl_entries.append(
                    self.get_gl_dict({
                        "account": d.account,
                        "account_currency": account_currency,
                        "against": self.party or self.paid_from,
                        "debit_in_account_currency": d.amount,
                        "debit": d.amount,
                        "cost_center": d.cost_center
                    })
                )

    def update_advance_paid(self):
        if self.payment_type in ("Receive", "Pay") and self.party:
            for d in self.get("references"):
                if d.allocated_amount and d.reference_doctype in ("Sales Order", "Purchase Order"):
                    frappe.get_doc(d.reference_doctype, d.reference_name).set_total_advance_paid()

    def update_expense_claim(self):
        if self.payment_type in ("Pay") and self.party:
            for d in self.get("references"):
                if d.reference_doctype == "Expense Claim" and d.reference_name:
                    doc = frappe.get_doc("Expense Claim", d.reference_name)
                    update_reimbursed_amount(doc)

    def set_concept(self):
        if not self.concept and (self.payment_type == "Miscellaneous Income" or
                                         self.payment_type == "Miscellaneous Expenditure"):
            frappe.throw(_("Concept is Mandatory in Miscellaneous Income/Expenditure"))
        if self.concept:
            return
        if self.payment_type == "Receive":
            self.concept = _("Receive from") + " " + _(self.party_type) + " " + self.party
        if self.payment_type == "Pay":
            self.concept = _("Pay to") + " " + _(self.party_type) + " " + self.party

    # Payment Lines
    def validate_payment_lines(self):
        # Remove empty lines
        self.set("lines", self.get("lines", {"paid_amount": ["not in", [0, None, ""]]}))

        total_amount = 0
        for line in self.get("lines"):
            self.validate_line_accounts(line)
            self.validate_mod_of_payment(line)

            self.validate_amount(line)
            total_amount += line.paid_amount

        if self.payment_type != "Internal Transfer" and (
                total_amount != self.paid_amount):

            frappe.throw(_("Remaining Amount must be zero"))

    def validate_line_accounts(self, line):
        paid_from_type = ["Receivable"] if (self.payment_type == "Receive" or
                                            self.payment_type == "Miscellaneous Income") else ["Bank", "Cash", "Check Wallet", "Document Wallet"]

        paid_to_type = ["Payable"] if (self.payment_type == "Pay" or
                                       self.payment_type == "Miscellaneous Expenditure") else ["Bank", "Cash", "Check Wallet", "Document Wallet"]
        if not line.paid_from:
            frappe.throw(_("{0} in Payment Line is mandatory").format("Paid From Account"))
        if not line.paid_to:
            frappe.throw(_("{0} in Payment Line is mandatory").format("Paid To Account"))
        self.validate_account_type(line.paid_from, paid_from_type)
        self.validate_account_type(line.paid_to, paid_to_type)

    def validate_mod_of_payment(self, line):
        if not frappe.db.exists("Mode of Payment", line.mode_of_payment):
            frappe.throw(_("Invalid Mode of Payment {0}").format(line.mode_of_payment))

    def validate_amount(self, line):
        if not line.paid_amount:
            frappe.throw(_("{0} in Payment Line is mandatory").format("Paid Amount"))

    def add_lines_bank_gl_entries(self, gl_entries):
        # Movements for bank checks mode of payments are generated separately
        for line in self.get("lines", {"mode_of_payment_type": ["not in", ["Bank Check", "Third Party Bank Check"]]}):
            self.generate_gl_bank_line(line, gl_entries)

    def generate_gl_bank_line(self, line, gl_entries):
        if self.payment_type == "Pay" or self.payment_type == "Miscellaneous Expenditure":
            gl_entries.append(
                self.get_gl_dict({
                    "account": line.paid_from,
                    "against": self.party if self.party else _("Miscellaneous Expenditure"),
                    "credit_in_account_currency": line.paid_amount,
                    "credit": line.paid_amount,
                    "concept": self.concept
                })
            )
        if self.payment_type == "Receive" or self.payment_type == "Miscellaneous Income":
            gl_entries.append(
                self.get_gl_dict({
                    "account": line.paid_to,
                    "against": self.party if self.party else _("Miscellaneous Income"),
                    "debit_in_account_currency": line.paid_amount,
                    "debit": line.paid_amount,
                    "concept": self.concept
                })
            )

    def add_lines_party_gl_entries(self, gl_entries):
        # Movements for bank checks are generated separately
        for line in self.get("lines", {"mode_of_payment": ["not in", ["Cheques propios", "Cheques de Terceros"]]}):
            self.generate_gl_party_line(line, gl_entries)

    def generate_gl_party_line(self, line, gl_entries):
        if self.payment_type == "Receive" or self.payment_type == "Miscellaneous Income":
            source_account = line.paid_from
            against_account = line.paid_to
            dr_or_cr = "credit"
        else:
            source_account = line.paid_to
            against_account = line.paid_from
            dr_or_cr = "debit"
        gl_dict = self.get_gl_dict({
            "account": source_account,
            "party": self.party if self.party else None,
            "party_type": self.party_type if self.party_type else None,
            "against": against_account,
            dr_or_cr: line.paid_amount,
            dr_or_cr + "_in_account_currency": line.paid_amount,
            "concept": self.concept
        })
        gl_entries.append(gl_dict)

    def validate_bank_checks(self):
        if self.payment_type == "Pay" or self.payment_type == "Miscellaneous Expenditure":
            self.validate_outgoing_checks()

        if self.payment_type != "Internal Transfer":
            self.validate_third_party_bank_checks()

    def validate_outgoing_checks(self):
        if self.get("checks_topay") != self.get("checks_acumulated"):
            frappe.throw(_("Total Amount Paid with checks must be equal to amount assigned to mode of payment Cheques propios"))

        if self.get("outgoing_bank_checks") and \
                not get_company_defaults(self.company).default_deferred_checks_account:

            frappe.throw(_("Default deferred checks account in Company is needed for outgoing Bank Checks"))

        for check in self.get("outgoing_bank_checks"):
            self.validate_check(check)

    def validate_check(self, check):
        for field in ["payment_date", "amount"]:
            if not check.get(field):
                label = frappe.get_meta("Bank Check").get_label(field)
                frappe.throw(_("{0} in Bank Check is mandatory").format(label))

    def validate_third_party_bank_checks(self):
        if self.get("third_party_bank_checks_topay") != self.get("third_party_bank_checks_acumulated"):
            frappe.throw(
                _("Total Amount Paid with documents must be equal to amount assigned to mode of payment Cheques de Terceros"))

        if self.payment_type == "Receive" or self.payment_type == "Miscellaneous Income":
            self.validate_new_third_party_bank_checks()
        else:
            self.validate_selected_third_party_bank_checks()

    def validate_new_third_party_bank_checks(self):
        for check in self.get("third_party_bank_checks"):
            self.validate_check(check)

    def validate_selected_third_party_bank_checks(self):
        for selected_check in self.get("selected_third_party_bank_checks"):
            docs = frappe.get_all("Bank Check", {"internal_number": selected_check.internal_number})
            # check must be unused
            if not docs or docs[0].used:
                frappe.throw(_("Check with Internal Number {0} was already used").format(selected_check.internal_number))

        # clear availables third party checks table
        self.set("third_party_bank_checks", None)

    def update_selected_third_party_bank_checks(self):
        for selected_check in self.get("selected_third_party_bank_checks"):
            docs = frappe.get_all("Bank Check", {"internal_number": selected_check.internal_number})
            # first doc contains selected_check info
            frappe.db.sql("""UPDATE `tabBank Check` set used=true WHERE name=%(name)s""", {"name": docs[0].name})

    def generate_gl_entries_for_bank_checks(self, gl_entries):

        if self.payment_type == "Pay" or self.payment_type == "Miscellaneous Expenditure":
            self.generate_gl_entries_for_outgoing_bank_checks(gl_entries)

        if self.payment_type != "Internal Transfer":
            self.generate_gl_entries_for_third_party_bank_checks(gl_entries)

    def generate_gl_entries_for_outgoing_bank_checks(self, gl_entries):

        company_defaults = get_company_defaults(self.company)

        acr = company_defaults.default_payable_account
        def_checks = company_defaults.default_deferred_checks_account

        check_lines = self.get("lines", {"mode_of_payment_type": ["=", "Bank Check"]})
        if not check_lines:
            return
        # get dest account of check line. All lines has the same dest account
        dest_account = check_lines[0].paid_to

        amount = self.get("checks_acumulated")
        gl_entries.append(
            self.get_gl_dict({
                "account": def_checks,
                "against": acr,
                "credit": amount,
                "credit_in_account_currency": amount,
                "concept": self.concept
            })
        )

        """gl_entries.append(
            self.get_gl_dict({
                "account": acr,
                "against": def_checks,
                "debit": amount,
                "debit_in_account_currency": amount,
                "concept": self.concept
            })
        ) """

        for check in self.get("outgoing_bank_checks"):
            gl_entries.append(
                self.get_gl_dict({
                    "account": check.account,
                    "against": def_checks,
                    "credit": check.amount,
                    "credit_in_account_currency": check.amount,
                    "concept": self.concept,
                    "posting_date" : check.payment_date
                })
            )
            gl_entries.append(
                self.get_gl_dict({
                    "account": def_checks,
                    "against": check.account,
                    "debit": check.amount,
                    "debit_in_account_currency": check.amount,
                    "concept": self.concept,
                    "posting_date": check.payment_date
                })
            )


    def generate_gl_entries_for_third_party_bank_checks(self, gl_entries):
        third_party_check_lines = self.get("lines", {"mode_of_payment_type": ["=", "Third Party Bank Check"], "paid_amount":
        ["!=", 0]})
        for line in third_party_check_lines:
            self.generate_gl_bank_line(line, gl_entries)


    def validate_documents(self):
        if self.payment_type == "Pay" or self.payment_type == "Miscellaneous Expenditure":
            self.validate_outgoing_documents()

        if self.payment_type != "Internal Transfer":
            self.validate_third_party_documents()

    def validate_outgoing_documents(self):
        for doc in self.get("documents"):
            self.validate_document(["date", "amount"], doc)

        if self.get("documents_topay") != self.get("documents_acumulated"):
            frappe.throw(
                _("Total Amount Paid with documents must be equal to amount assigned to mode of payment Documentos propios"))

    def validate_third_party_documents(self):
        if self.get("third_party_documents_topay") != self.get("third_party_documents_acumulated"):
            frappe.throw(
                _("Total Amount Paid with documents must be equal to amount assigned to mode of payment Documentos de Terceros"))

        if self.payment_type == "Receive" or self.payment_type == "Miscellaneous Income":
            self.validate_new_third_party_documents()
        if self.payment_type == "Pay" or self.payment_type == "Miscellaneous Expenditure":
            self.validate_selected_third_party_documents()

    def validate_new_third_party_documents(self):
        for doc in self.get("third_party_documents"):
            self.validate_document(["date", "amount", "internal_number"], doc)

    def validate_document(self, mandatory_fields, doc):
        for field in mandatory_fields:
            label = frappe.get_meta("Document").get_label(field)
            if not doc.get(field):
                frappe.throw(_("{0} in Document is mandatory").format(label))


    def validate_selected_third_party_documents(self):
        for document in self.get("selected_third_party_documents"):
            docs = frappe.get_all("Document", {"internal_number": document.internal_number})
            # check must be unused
            if not docs or docs[0].used:
                frappe.throw(
                    _("Document with Internal Number {0} was already used").format(document.internal_number))


    def update_selected_third_party_documents(self):
        for document in self.get("selected_third_party_documents"):
            docs = frappe.get_all("Document", {"internal_number": document.internal_number})

            # first doc contains selected_document info
            frappe.db.sql("""UPDATE `tabDocument` set used=true WHERE name=%(name)s""", {"name": docs[0].name})


    def save_outgoing_bank_checks(self):
        for check in self.get("outgoing_bank_checks"):
            bank_check = frappe.new_doc("Bank Check")
            bank_check.third_party_check = False
            bank_check.used = True
            bank_check.account = check.account
            self.copy_check_info(bank_check, check)
            bank_check.save()
            bank_check.submit()

    def save_new_third_party_bank_checks(self):
        if self.payment_type in ["Miscellaneous Expenditure", "Pay", "Internal Transfer"]:
            return
        for check in self.get("third_party_bank_checks"):
            bank_check = frappe.new_doc("Bank Check")
            bank_check.third_party_check = True
            bank_check.used = False
            bank_check.bank = check.bank
            bank_check.internal_number = check.internal_number
            self.copy_check_info(bank_check, check)
            bank_check.save()
            bank_check.submit()

    def copy_check_info(self, bank_check, check):
        bank_check.issue_date = self.posting_date
        bank_check.concept = self.concept
        bank_check.number = check.number
        bank_check.amount = check.amount
        bank_check.payment_date = check.payment_date
        bank_check.company = self.company

        # save party type and party in bank check
        if self.party_type and self.party:
            bank_check.party_type = self.party_type
            bank_check.party = self.party

    def save_documents(self):
        if self.payment_type in ["Miscellaneous Expenditure", "Pay"]:
            for doc in self.get("documents"):
                new_document = frappe.new_doc("Document")
                new_document.third_party = False
                self.copy_doc_info(new_document, doc)
                new_document.save()

        if self.payment_type in ["Miscellaneous Income", "Receive"]:
            for doc in self.get("third_party_documents"):
                new_document = frappe.new_doc("Document")
                new_document.third_party = True
                new_document.used = False
                self.copy_doc_info(new_document, doc)
                new_document.save()

    def copy_doc_info(self, new_document, doc):
        new_document.company = self.company
        new_document.amount = doc.amount
        new_document.client_detail = doc.client_detail
        new_document.date = doc.date
        new_document.internal_number = doc.internal_number


    def validate_internal_transfer(self):
        if not self.paid_from or not self.paid_to:
            frappe.throw(_("Paid From account and Paid To account are mandatory in Internal Transfer"))

        account_details = get_account_details(self.paid_from, self.posting_date)
        if account_details.account_type == "Check Wallet":
            if self.paid_amount != self.third_party_bank_checks_acumulated:
                frappe.throw(_("Total amount of selected checks must be equal to paid amount"))
            self.validate_selected_third_party_bank_checks()

        if account_details.account_type == "Document Wallet":
            if self.paid_amount != self.third_party_documents_acumulated:
                frappe.throw(_("Total amount of selected documents must be equal to paid amount"))
            self.validate_selected_third_party_documents()




@frappe.whitelist()
def get_outstanding_reference_documents(args):
    args = json.loads(args)

    party_account_currency = get_account_currency(args.get("party_account"))
    company_currency = frappe.db.get_value("Company", args.get("company"), "default_currency")

    # Get negative outstanding sales /purchase invoices
    total_field = "base_grand_total" if party_account_currency == company_currency else "grand_total"

    negative_outstanding_invoices = get_negative_outstanding_invoices(args.get("party_type"),
                                                                      args.get("party"), args.get("party_account"),
                                                                      total_field)

    # Get positive outstanding sales /purchase invoices
    outstanding_invoices = get_outstanding_invoices(args.get("party_type"), args.get("party"),
                                                    args.get("party_account"))

    for d in outstanding_invoices:
        d["exchange_rate"] = 1
        if party_account_currency != company_currency:
            if d.voucher_type in ("Sales Invoice", "Purchase Invoice", "Expense Claim"):
                d["exchange_rate"] = frappe.db.get_value(d.voucher_type, d.voucher_no, "conversion_rate")
            elif d.voucher_type == "Journal Entry":
                d["exchange_rate"] = get_exchange_rate(
                    party_account_currency, company_currency, d.posting_date
                )

    # Get all SO / PO which are not fully billed or aginst which full advance not paid
    orders_to_be_billed = get_orders_to_be_billed(args.get("posting_date"), args.get("party_type"), args.get("party"),
                                                  party_account_currency, company_currency)

    return negative_outstanding_invoices + outstanding_invoices + orders_to_be_billed


def get_orders_to_be_billed(posting_date, party_type, party, party_account_currency, company_currency):
    if party_type == "Customer":
        voucher_type = 'Sales Order'
    elif party_type == "Supplier":
        voucher_type = 'Purchase Order'
    elif party_type == "Employee":
        voucher_type = None

    orders = []
    if voucher_type:
        ref_field = "base_grand_total" if party_account_currency == company_currency else "grand_total"

        orders = frappe.db.sql("""
            select
                name as voucher_no,
                {ref_field} as invoice_amount,
                ({ref_field} - advance_paid) as outstanding_amount,
                transaction_date as posting_date
            from
                `tab{voucher_type}`
            where
                {party_type} = %s
                and docstatus = 1
                and ifnull(status, "") != "Closed"
                and {ref_field} > advance_paid
                and abs(100 - per_billed) > 0.01
            order by
                transaction_date, name
            """.format(**{
            "ref_field": ref_field,
            "voucher_type": voucher_type,
            "party_type": scrub(party_type)
        }), party, as_dict=True)

    order_list = []
    for d in orders:
        d["voucher_type"] = voucher_type
        # This assumes that the exchange rate required is the one in the SO
        d["exchange_rate"] = get_exchange_rate(party_account_currency,
                                               company_currency, posting_date)
        order_list.append(d)

    return order_list


def get_negative_outstanding_invoices(party_type, party, party_account, total_field):
    if party_type != "Employee":
        voucher_type = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"
        return frappe.db.sql("""
            select
                "{voucher_type}" as voucher_type, name as voucher_no,
                {total_field} as invoice_amount, outstanding_amount, posting_date,
                due_date, conversion_rate as exchange_rate
            from
                `tab{voucher_type}`
            where
                {party_type} = %s and {party_account} = %s and docstatus = 1 and outstanding_amount < 0
            order by
                posting_date, name
            """.format(**{
            "total_field": total_field,
            "voucher_type": voucher_type,
            "party_type": scrub(party_type),
            "party_account": "debit_to" if party_type == "Customer" else "credit_to"
        }), (party, party_account), as_dict=True)
    else:
        return []


@frappe.whitelist()
def get_party_details(company, party_type, party, date):
    if not frappe.db.exists(party_type, party):
        frappe.throw(_("Invalid {0}: {1}").format(party_type, party))

    party_account = get_party_account(party_type, party, company)

    account_currency = get_account_currency(party_account)
    account_balance = get_balance_on(party_account, date)
    party_balance = get_balance_on(party_type=party_type, party=party)

    return {
        "party_account": party_account,
        "party_account_currency": account_currency,
        "party_balance": party_balance,
        "account_balance": account_balance
    }


@frappe.whitelist()
def get_account_details(account, date):
    frappe.has_permission('Payment Entry', throw=True)
    return frappe._dict({
        "account_currency": get_account_currency(account),
        "account_balance": get_balance_on(account, date),
        "account_type": frappe.db.get_value("Account", account, "account_type")
    })


@frappe.whitelist()
def get_company_defaults(company):
    fields = ["write_off_account", "exchange_gain_loss_account", "cost_center", "default_payable_account",
              "default_receivable_account", "default_deferred_checks_account"]
    ret = frappe.db.get_value("Company", company, fields, as_dict=1)

    # get currency of default accounts
    ret.update({"default_receivable_account_currency": get_account_currency(ret.default_receivable_account),
                "default_payable_account_currency": get_account_currency(ret.default_payable_account)});

    for fieldname in fields:
        if not ret[fieldname]:
            frappe.throw(_("Please set default {0} in Company {1}")
                         .format(frappe.get_meta("Company").get_label(fieldname), company))

    return ret


@frappe.whitelist()
def get_reference_details(reference_doctype, reference_name, party_account_currency):
    total_amount = outstanding_amount = exchange_rate = None
    ref_doc = frappe.get_doc(reference_doctype, reference_name)

    if reference_doctype not in ["Journal Entry", "Eventual Purchase Invoice", "Operation Completion"]:
        if party_account_currency == ref_doc.company_currency:
            if ref_doc.doctype == "Expense Claim":
                total_amount = ref_doc.total_sanctioned_amount
            else:
                total_amount = ref_doc.base_grand_total
            exchange_rate = 1
        else:
            total_amount = ref_doc.grand_total

            # Get the exchange rate from the original ref doc
            # or get it based on the posting date of the ref doc
            exchange_rate = ref_doc.get("conversion_rate") or \
                            get_exchange_rate(party_account_currency, ref_doc.company_currency, ref_doc.posting_date)

        outstanding_amount = ref_doc.get("outstanding_amount") \
            if reference_doctype in ("Sales Invoice", "Purchase Invoice", "Expense Claim") \
            else flt(total_amount) - flt(ref_doc.advance_paid)

    elif reference_doctype == "Journal Entry":
        # Get the exchange rate based on the posting date of the ref doc
        exchange_rate = get_exchange_rate(party_account_currency,
                                          ref_doc.company_currency, ref_doc.posting_date)

    # reference_doctype is Eventual Purchase Invoice or Operation Completion
    else:
        exchange_rate = 1
        total_amount = ref_doc.total_amount
        outstanding_amount = ref_doc.outstanding_amount


    return frappe._dict({
        "due_date": ref_doc.get("due_date") if reference_doctype != "Eventual Purchase Invoice" else ref_doc.get("issue_date"),
        "posting_date": ref_doc.get("posting_date"),
        "total_amount": total_amount,
        "outstanding_amount": outstanding_amount,
        "exchange_rate": exchange_rate
    })


@frappe.whitelist()
def get_payment_entry(dt, dn, party_amount=None, bank_account=None, bank_amount=None):
    doc = frappe.get_doc(dt, dn)

    if dt in ("Sales Order", "Purchase Order") and flt(doc.per_billed, 2) > 0:
        frappe.throw(_("Can only make payment against unbilled {0}").format(dt))

    if dt in ("Sales Invoice", "Sales Order"):
        party_type = "Customer"
    elif dt in ("Purchase Invoice", "Purchase Order"):
        party_type = "Supplier"
    elif dt in ("Expense Claim"):
        party_type = "Employee"

    # party account
    if dt == "Sales Invoice":
        party_account = doc.debit_to
    elif dt == "Purchase Invoice":
        party_account = doc.credit_to
    else:
        party_account = get_party_account(party_type, doc.get(party_type.lower()), doc.company)

    party_account_currency = doc.get("party_account_currency") or get_account_currency(party_account)

    # payment type
    if (dt == "Sales Order" or (dt == "Sales Invoice" and doc.outstanding_amount > 0)) \
            or (dt == "Purchase Invoice" and doc.outstanding_amount < 0):
        payment_type = "Receive"
    else:
        payment_type = "Pay"

    # amounts
    grand_total = outstanding_amount = 0
    if party_amount:
        grand_total = outstanding_amount = party_amount
    elif dt in ("Sales Invoice", "Purchase Invoice"):
        grand_total = doc.base_grand_total if party_account_currency == doc.company_currency else doc.grand_total
        outstanding_amount = doc.outstanding_amount
    elif dt in ("Expense Claim"):
        grand_total = doc.total_sanctioned_amount
        outstanding_amount = doc.total_sanctioned_amount - doc.total_amount_reimbursed
    else:
        total_field = "base_grand_total" if party_account_currency == doc.company_currency else "grand_total"
        grand_total = flt(doc.get(total_field))
        outstanding_amount = grand_total - flt(doc.advance_paid)

    # bank or cash
    bank = get_default_bank_cash_account(doc.company, "Bank", mode_of_payment=doc.get("mode_of_payment"),
                                         account=bank_account)

    paid_amount = received_amount = 0
    if party_account_currency == bank.account_currency:
        paid_amount = received_amount = abs(outstanding_amount)
    elif payment_type == "Receive":
        paid_amount = abs(outstanding_amount)
        if bank_amount:
            received_amount = bank_amount
    else:
        received_amount = abs(outstanding_amount)
        if bank_amount:
            paid_amount = bank_amount

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = payment_type
    pe.company = doc.company
    pe.posting_date = nowdate()
    pe.mode_of_payment = doc.get("mode_of_payment")
    pe.party_type = party_type
    pe.party = doc.get(scrub(party_type))
    pe.paid_from = party_account if payment_type == "Receive" else bank.account
    pe.paid_to = party_account if payment_type == "Pay" else bank.account
    pe.paid_from_account_currency = party_account_currency \
        if payment_type == "Receive" else bank.account_currency
    pe.paid_to_account_currency = party_account_currency if payment_type == "Pay" else bank.account_currency
    pe.paid_amount = paid_amount
    pe.received_amount = received_amount
    pe.allocate_payment_amount = 1
    pe.letter_head = doc.get("letter_head")

    pe.append("references", {
        "reference_doctype": dt,
        "reference_name": dn,
        "due_date": doc.get("due_date"),
        "posting_date": doc.get("posting_date"),
        "total_amount": grand_total,
        "outstanding_amount": outstanding_amount,
        "allocated_amount": outstanding_amount
    })

    pe.setup_party_account_field()
    pe.set_missing_values()
    if party_account and bank:
        pe.set_exchange_rate()
        pe.set_amounts()
    return pe


@frappe.whitelist()
def get_payment_entry_for_eventual_purchase_invoice(docname):
    doc = frappe.get_doc("Eventual Purchase Invoice", docname)

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Miscellaneous Expenditure"
    pe.party_type = None
    pe.company = doc.company
    pe.posting_date = nowdate()
    pe.paid_amount = doc.outstanding_amount
    pe.base_paid_amount = doc.outstanding_amount
    pe.concept = _("Pay to Supplier {0}".format(doc.supplier_name))

    pe.append("references", {
        "reference_doctype": "Eventual Purchase Invoice",
        "reference_name": docname,
        "total_amount": doc.total_amount,
        "outstanding_amount": doc.outstanding_amount,
        "allocated_amount": doc.outstanding_amount,
        "posting_date": doc.issue_date
    })
    return pe


@frappe.whitelist()
def get_mod_of_payments(company, payment_type):
    mode_of_payments = frappe.db.sql("""select t1.parent as name, type from `tabMode of Payment Account` as t1 inner join `tabMode of Payment` as t2 on t1.parent = t2.name
    where t1.parenttype=%(parenttype)s and t1.company=%(company)s order by name""",
                         {"parenttype": "Mode of Payment", "company": company}, as_dict=1)

    if payment_type == "income":
        return filter(lambda x: (x.type != "Bank Check") and (x.type != "Document"), mode_of_payments)

    return mode_of_payments
