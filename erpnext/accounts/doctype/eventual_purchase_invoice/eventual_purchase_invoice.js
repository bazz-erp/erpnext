
frappe.ui.form.on("Eventual Purchase Invoice", {

    refresh: function (frm) {
        if(frm.docstatus == 1) {
            this.frm.add_custom_button(__('Payment'), this.make_payment_entry);
            }
    }
})