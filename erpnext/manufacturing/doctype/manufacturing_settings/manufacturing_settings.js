
frappe.ui.form.on('Manufacturing Settings', {

    onload: function (frm) {
        frappe.call({
           method: "erpnext.manufacturing.doctype.manufacturing_settings.manufacturing_settings.get_all_item_groups",
           callback: function (r) {
               $.each(r.message, function (index, item_group) {
                   checkbox = has_item_group_checked(frm,item_group.name) ? $(`<input type="checkbox" checked="" data-value="${item_group.name}"/>`):
                   $(`<input type="checkbox" data-value="${item_group.name}"/>`);

                   frm.get_field("item_groups_html").$wrapper.append($(`<div class="list-item">
						<div class="list-item__content list-item__content--flex-2">
								<label>
                                    ${checkbox[0].outerHTML}
                                    ${item_group.name}
								</label>
							</div>
						</div>`));
               });
               frm.get_field("item_groups_html").$wrapper.find("input[type='checkbox']").change( function () {
                    frm.dirty();
                    set_item_groups_checked(frm);
                });
           }
        });


    },

});

var has_item_group_checked = function (frm, i_group) {
    item_groups = $(frm.doc.item_groups_table).filter(function (index, row) {
        return row.item_group == i_group;

    });
    return item_groups.length > 0;
}

var set_item_groups_checked = function (frm) {
    frm.clear_table("item_groups_table");
    refresh_field("item_groups_table");
    frm.get_field("item_groups_html").$wrapper.find("input[type='checkbox']:checked").each(function (index, checkbox) {
           row = frm.add_child("item_groups_table");
           row.item_group = $(checkbox).attr('data-value');
        });

}