frappe.listview_settings['Operation Completion'] = {
    get_indicator: function (doc) {
        if (doc.status == "Pending") {
            return [__("Pending"), "orange", "status,=,Pending"];
        }
        if (doc.status == "In Process") {
            return [__("In Process"), "orange", "status,=,In Process"];
        }

        if (doc.status == "Completed") {
            return [__("Completed"), "green", "status,=,Completed"];
        }
    }
};