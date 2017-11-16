frappe.listview_settings['Bank Check'] = {

    onload: function (listview) {
        	frappe.route_options ={"used": ["=", false], "third_party_check": ["=",true]};
	}

};