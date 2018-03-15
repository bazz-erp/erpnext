// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Production Order", {
	setup: function(frm) {
		frm.custom_make_buttons = {
			'Timesheet': 'Make Timesheet',
			'Stock Entry': 'Make Stock Entry',
		}
		
		// Set query for warehouses
		frm.set_query("wip_warehouse", function(doc) {
			return {
				filters: {
					'company': frm.doc.company,
				}
			}
		});
		
		frm.set_query("source_warehouse", "required_items", function() {
			return {
				filters: {
					'company': frm.doc.company,
				}
			}
		});
		
		frm.set_query("fg_warehouse", function() {
			return {
				filters: {
					'company': frm.doc.company,
					'is_group': 0
				}
			}
		});
		
		frm.set_query("scrap_warehouse", function() {
			return {
				filters: {
					'company': frm.doc.company,
					'is_group': 0
				}
			}
		});
		
		// Set query for BOM
		frm.set_query("bom_no", function() {
			if (frm.doc.production_item) {
				return{
					query: "erpnext.controllers.queries.bom",
					filters: {item: cstr(frm.doc.production_item)}
				}
			} else msgprint(__("Please enter Production Item first"));
		});
		
		// Set query for FG Item
		frm.set_query("production_item", function() {
			return {
				query: "erpnext.controllers.queries.item_query",
				filters:{
					'is_stock_item': 1,
				}
			}
		});

		// Set query for FG Item
		frm.set_query("project", function() {
			return{
				filters:[
					['Project', 'status', 'not in', 'Completed, Cancelled']
				]
			}
		});
	},
	
	onload: function(frm) {
		if (!frm.doc.status)
			frm.doc.status = 'Draft';

		frm.add_fetch("sales_order", "project", "project");

		if(frm.doc.__islocal) {
			frm.set_value({
				"actual_start_date": "",
				"actual_end_date": ""
			});
			erpnext.production_order.set_default_warehouse(frm);
		}

		// formatter for production order operation
		frm.set_indicator_formatter('operation',
			function(doc) { return (frm.doc.qty==doc.completed_qty) ? "green" : "orange" });
	},

	refresh: function(frm) {
		erpnext.toggle_naming_series();
		erpnext.production_order.set_custom_buttons(frm);
		frm.set_intro("");

		if (frm.doc.docstatus === 0 && !frm.doc.__islocal) {
			frm.set_intro(__("Submit this Production Order for further processing."));
		}

		if (frm.doc.docstatus===1) {
			frm.trigger('show_progress');
		}

		if(frm.doc.docstatus == 1 && frm.doc.status != 'Stopped'){
			frm.add_custom_button(__('Make Timesheet'), function(){
				frappe.model.open_mapped_doc({
					method: "erpnext.manufacturing.doctype.production_order.production_order.make_new_timesheet",
					frm: cur_frm
				})
			})
		}

	},
	
	show_progress: function(frm) {
		var bars = [];
		var message = '';
		var added_min = false;

		// produced qty
		var title = __('{0} items produced', [frm.doc.produced_qty]);
		bars.push({
			'title': title,
			'width': (frm.doc.produced_qty / frm.doc.qty * 100) + '%',
			'progress_class': 'progress-bar-success'
		});
		if (bars[0].width == '0%') {
			bars[0].width = '0.5%';
			added_min = 0.5;
		}
		message = title;

		// pending qty
		if(!frm.doc.skip_transfer){
			var pending_complete = frm.doc.material_transferred_for_manufacturing - frm.doc.produced_qty;
			if(pending_complete) {
				var title = __('{0} items in progress', [pending_complete]);
				bars.push({
					'title': title,
					'width': ((pending_complete / frm.doc.qty * 100) - added_min)  + '%',
					'progress_class': 'progress-bar-warning'
				})
				message = message + '. ' + title;
			}
		}
		frm.dashboard.add_progress(__('Status'), bars, message);
	},
	
	production_item: function(frm) {
		if (frm.doc.production_item) {
			frappe.call({
				method: "erpnext.manufacturing.doctype.production_order.production_order.get_item_details",
				args: {
					item: frm.doc.production_item,
					project: frm.doc.project
				},
				callback: function(r) {
					if(r.message) {
						erpnext.in_production_item_onchange = true;
						$.each(["description", "stock_uom", "project", "bom_no"], function(i, field) {
							frm.set_value(field, r.message[field]);
						});

						if(r.message["set_scrap_wh_mandatory"]){
							frm.toggle_reqd("scrap_warehouse", true);
						}
						erpnext.in_production_item_onchange = false;
					}
				}
			});
		}
	},
	
	project: function(frm) {
		if(!erpnext.in_production_item_onchange) {
			frm.trigger("production_item");
		}
	},
	
	bom_no: function(frm) {
		return frm.call({
			doc: frm.doc,
			method: "get_items_and_operations_from_bom",
			callback: function(r) {
				if(r.message["set_scrap_wh_mandatory"]){
					frm.toggle_reqd("scrap_warehouse", true);
				}
			}
		});
	},
	
	use_multi_level_bom: function(frm) {
		if(frm.doc.bom_no) {
			frm.trigger("bom_no");
		}
	},

	qty: function(frm) {
		frm.trigger('bom_no');
	},
	
	before_submit: function(frm) {
		frm.toggle_reqd(["fg_warehouse", "wip_warehouse"], true);
		frm.fields_dict.required_items.grid.toggle_reqd("source_warehouse", true);
	}
});

frappe.ui.form.on("Production Order Item", {
	source_warehouse: function(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if(!row.item_code) {
			frappe.throw(__("Please set the Item Code first"));
		} else if(row.source_warehouse) {
			frappe.call({
				"method": "erpnext.stock.utils.get_latest_stock_qty",
				args: {
					item_code: row.item_code,
					warehouse: row.source_warehouse
				},
				callback: function (r) {			
					frappe.model.set_value(row.doctype, row.name,
						"available_qty_at_source_warehouse", r.message);
				}
			})
		}
	}
})

frappe.ui.form.on("Production Order Operation", {
	workstation: function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if (d.workstation) {
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "Workstation",
					name: d.workstation
				},
				callback: function (data) {
					frappe.model.set_value(d.doctype, d.name, "hour_rate", data.message.hour_rate);
					erpnext.production_order.calculate_cost(frm.doc);
					erpnext.production_order.calculate_total_cost(frm);
				}
			})
		}
	},
	time_in_mins: function(frm, cdt, cdn) {
		erpnext.production_order.calculate_cost(frm.doc);
		erpnext.production_order.calculate_total_cost(frm);
	},
	    //frappe.set_route("Form","Operation Completion", op.completion);
});

erpnext.production_order = {
	set_custom_buttons: function(frm) {
		var doc = frm.doc;
		if (doc.docstatus === 1) {
			if (doc.status != 'Stopped' && doc.status != 'Completed') {
				frm.add_custom_button(__('Stop'), function() {
					erpnext.production_order.stop_production_order(frm, "Stopped");
				}, __("Status"));
			} else if (doc.status == 'Stopped') {
				frm.add_custom_button(__('Re-open'), function() {
					erpnext.production_order.stop_production_order(frm, "Resumed");
				}, __("Status"));
			}

			if(!frm.doc.skip_transfer){
				if ((flt(doc.material_transferred_for_manufacturing) < flt(doc.qty))
					&& frm.doc.status != 'Stopped') {
					frm.has_start_btn = true;
					var start_btn = frm.add_custom_button(__('Start'), function() {
						erpnext.production_order.make_se(frm, 'Material Transfer for Manufacture');
					});
					start_btn.addClass('btn-primary');
				}
			}

			if(!frm.doc.skip_transfer){
				if ((flt(doc.produced_qty) < flt(doc.material_transferred_for_manufacturing))
						&& frm.doc.status != 'Stopped') {
					frm.has_finish_btn = true;
					var finish_btn = frm.add_custom_button(__('Finish'), function() {
						erpnext.production_order.make_se(frm, 'Manufacture');
					});

					if(doc.material_transferred_for_manufacturing==doc.qty) {
						// all materials transferred for manufacturing, make this primary
						finish_btn.addClass('btn-primary');
					}
				}
			} else {
				if ((flt(doc.produced_qty) < flt(doc.qty)) && frm.doc.status != 'Stopped') {
					frm.has_finish_btn = true;
					var finish_btn = frm.add_custom_button(__('Finish'), function() {
						erpnext.production_order.make_se(frm, 'Manufacture');
					});
					finish_btn.addClass('btn-primary');
				}
			}
		}

	},
	calculate_cost: function(doc) {
		if (doc.operations){
			var op = doc.operations;
			doc.planned_operating_cost = 0.0;
			for(var i=0;i<op.length;i++) {
				var planned_operating_cost = flt(flt(op[i].hour_rate) * flt(op[i].time_in_mins) / 60, 2);
				frappe.model.set_value('Production Order Operation', op[i].name,
					"planned_operating_cost", planned_operating_cost);
				doc.planned_operating_cost += planned_operating_cost;
			}
			refresh_field('planned_operating_cost');
		}
	},

	calculate_total_cost: function(frm) {
		var variable_cost = frm.doc.actual_operating_cost ?
			flt(frm.doc.actual_operating_cost) : flt(frm.doc.planned_operating_cost)
		frm.set_value("total_operating_cost", (flt(frm.doc.additional_operating_cost) + variable_cost))
	},

	set_default_warehouse: function(frm) {
		if (!(frm.doc.wip_warehouse || frm.doc.fg_warehouse)) {
			frappe.call({
				method: "erpnext.manufacturing.doctype.production_order.production_order.get_default_warehouse",
				callback: function(r) {
					if(!r.exe) {
						frm.set_value("wip_warehouse", r.message.wip_warehouse);
						frm.set_value("fg_warehouse", r.message.fg_warehouse)
					}
				}
			});
		}
	},
	
	make_se: function(frm, purpose) {
		if(!frm.doc.skip_transfer){
			var max = (purpose === "Manufacture") ?
				flt(frm.doc.material_transferred_for_manufacturing) - flt(frm.doc.produced_qty) :
				flt(frm.doc.qty) - flt(frm.doc.material_transferred_for_manufacturing);
		} else {
			var max = flt(frm.doc.qty) - flt(frm.doc.produced_qty);
		}

		// BAZZ - removed dialog that prompts qty to manufacture. All products are manufactured at once

				frappe.call({
					method:"erpnext.manufacturing.doctype.production_order.production_order.make_stock_entry",
					args: {
						"production_order_id": frm.doc.name,
						"purpose": purpose,
						"qty": max
					},
					callback: function(r) {
						var doclist = frappe.model.sync(r.message);
						frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
					}
				});
	},
	
	stop_production_order: function(frm, status) {
		frappe.call({
			method: "erpnext.manufacturing.doctype.production_order.production_order.stop_unstop",
			args: {
				production_order: frm.doc.name,
				status: status
			},
			callback: function(r) {
				if(r.message) {
					frm.set_value("status", r.message);
					frm.reload_doc();
				}
			}
		})
	}
}

var create_start_operation_dialog = function (frm, operation) {

    operation_details = get_operation_by_name(frm, operation).doc;

    var items = [{item_code : frm.doc.production_item,
                        item_name: frm.doc.production_item_name}];
	items = items.concat(frm.doc.required_items);

	/**var html = $(`
				<div style="border: 1px solid #d1d8dd" data-attribute="items_supplied">
					<div class="list-item list-item--head">
						<div class="list-item__content list-item__content--flex-2">
							${__("Materials supplied")}
						</div>
					</div>
					${items.map(item => `
						<div class="list-item">
							<div class="list-item__content list-item__content--flex-2">
								<label class="control-label">
								${item.item_name}
								</label>
								<input type="text" data-fieldname="qty" data-item="${item.item_code}" class="form-control bold" data-fieldtype="Float"/>
							</div>
						</div>
					`).join("")}
				</div>
			`); */

    var fields = [
    {
        label: __("Materials Supplied"),
        fieldtype: "Section Break",
        fieldname: "materials_supplied_section"
    }];
    $.each(items, function (i, item) {
        fields.push({
            label:item.item_code.toString() + " - " + item.item_name,
            fieldtype: "Float",
            fieldname: item.item_code.toString(),
            reqd: 0,
            default: "0"
        });
    });

    fields.push(
    {
        fieldtype: "Section Break",
        fieldname: "workshop_section"
    });

    fields.push(
    {
		fieldname: "workshop",
		fieldtype: "Link",
		options: "Supplier",
		label: __("Workshop"),
        reqd: 1,
		get_query: function(doc) {
            return {
                filters: {
                    'supplier_type': 'Taller',
                }
            }
        }
    });

	var dialog = new frappe.ui.Dialog({
		title: __("Send Materials"),
		fields: fields
	});

	// Workshop must be selected once when operation is Pending. If operation is 'In Process' workshop is read-only field
    if (operation_details.status == 'In Process') {
        console.log(dialog.fields_dict["workshop"]);
        dialog.fields_dict["workshop"].df.read_only = 1;
        dialog.set_value("workshop", operation_details.workshop);

    }
    else if (operation_details.status == 'Pending') {
        debugger;
        dialog.set_value("workshop", frm.doc.default_workshop);
    }
    dialog.fields_dict["workshop"].refresh();

	// get materials received in previous operation
    previous_operation = $(cur_frm.doc.operations).filter(function (i, op) {
       return op.idx == (operation_details.idx - 1);
    });

    // If previous operation not exist
    if (previous_operation.length == 0) {
        $.each(cur_frm.doc.required_items, function (i, item) {
           dialog.set_value(item.item_code, item.required_qty);
        });
    }
    else {
        // get materials availables to be sent to the workshop based on items received in previous operation
        previous_operation = previous_operation[0];
        frappe.call({
           method: "erpnext.manufacturing.doctype.operation_completion.operation_completion.get_available_materials",
            args: {
               	operation_id: operation_details.completion,
           		previous_operation_id: previous_operation.completion
            },
            callback: function (r) {
              if (r.message) {
                   $.each(r.message, function (i, item) {
                    dialog.set_value(item.item_code, item.item_qty)
                   });

              }
            }
        });
    }

	dialog.set_primary_action(__("Confirm"),function () {
	    var items_supplied = dialog.get_values();

	    // removes workshop key from json object
	    delete items_supplied["workshop"];

	    /**	items_supplied = dialog.wrapper.find("input[data-fieldname='qty']").map( function (i, el) {
             return {item_code: $(el).attr('data-item'), qty: $(el).val()}; }).toArray();*/

		console.log(items_supplied);

		frappe.call({
			method: "erpnext.manufacturing.doctype.production_order.production_order.start_operation",
			args: {
				operation_id: operation,
				workshop: dialog.get_value("workshop"),
				items_supplied: items_supplied
			},
			callback: function (r) {
			    frm.reload_doc();
				dialog.hide();
            }
		});
	});

	dialog.show();
}

var create_finish_operation_dialog = function (operation) {

    var dialog = new frappe.ui.Dialog({
		title: __("Receive materials"),
		fields: [
			{
				fieldname: "items_received_section",
				fieldtype: "Section Break",
				label: __("Items Received")
			},
            {
                fieldname: cur_frm.doc.production_item.toString(),
                label: cur_frm.doc.production_item.toString() + " - " + cur_frm.doc.production_item_name,
                fieldtype: "Float",
                default: "0"
            },
            {
				fieldname: "cost_section",
				fieldtype: "Section Break"
			},
            {
				fieldname: "operating_cost",
				fieldtype: "Currency",
				label: __("Operating Cost"),
				default: "0"
			}]
	});

    //calculate_production_item_remaining_qty(operation,dialog);


    dialog.get_input(cur_frm.doc.production_item.toString()).on("focusout", function () {
       dialog.set_value("operating_cost", (operation.operating_cost * dialog.get_value(cur_frm.doc.production_item))/ cur_frm.doc.bom_produced_qty);
       dialog.fields_dict["operating_cost"].refresh();
    });
	
	dialog.set_primary_action(__("Confirm"), function () {
		var items_received = dialog.get_values();
		delete items_received["operating_cost"];

	    frappe.call({
			method: "erpnext.manufacturing.doctype.production_order.production_order.finish_operation",
			args: {
				operation_id: operation.name,
				operating_cost: dialog.get_value("operating_cost"),
				items_received: items_received
			},
			callback: function (r) {
			    cur_frm.reload_doc();
			    dialog.hide();

            }
		});
    });
	dialog.show();

}
var get_operation_by_name = function (frm, operation_name) {
	return frm.fields_dict["operations"].grid.grid_rows_by_docname[operation_name]
}
var update_operations_action = function (frm) {

	$.each(frm.doc.operations, function (i, operation) {

	    var send_disabled = ["Pending", "In Process"].includes(operation.status) ? "" : "disabled";
	    var receive_disabled = operation.status == "In Process" ? "" : "disabled";

		var start_button = "<button operation='" + operation.name + "' class='btn btn-secondary btn-xs _operation_send' " + send_disabled + ">Enviar</button>";
		var finish_button = "<button operation='" + operation.name + "' class='btn btn-secondary btn-xs _operation_receive' " + receive_disabled + ">Recibir</button>";

		wrapper = get_operation_by_name(frm, operation.name).wrapper.find("div[data-fieldname='test_button'] .static-area");
		wrapper.html(start_button + " " + finish_button);

    });

	$("._operation_send").off();
	$("._operation_send").on('click', function () {
		create_start_operation_dialog(frm, $(this).attr('operation'));
	});

	$("._operation_receive").off();
	$("._operation_receive").on('click', function () {
		var op = get_operation_by_name(cur_frm, $(this).attr('operation')).doc;
		create_finish_operation_dialog(op);
	});

}

/**
 * iterates required items and set its qty to dialogs fields
 * @param dialog
 * @param required_items
 */
var setup_materials_qty_for_start_operation = function (dialog, required_items) {
    $.each(required_items, function (index) {

    })
}

/**
 * calculates remainig qty of production item that must be received from the workshop, and populates the dialog with this value
 * @param dialog
 */
var calculate_production_item_remaining_qty  = function (operation, dialog) {
    frappe.call({
        method: "erpnext.manufacturing.doctype.operation_completion.operation_completion.calculate_production_item_remaining_qty",
        args: {
            operation_id: operation.completion
        },
        callback: function (r) {
            item_qty = r.message ? r.message: 0;
            dialog.set_value(cur_frm.doc.production_item, item_qty );
            dialog.set_value("operating_cost", (operation.operating_cost * item_qty)/ cur_frm.doc.bom_produced_qty);
        }
    });
};

