frappe.ui.form.on("Vendor Registration", {
    refresh(frm) {
        if (frm.is_new()) {
            return;
        }

        if (frm.doc.supplier) {
            return;
        }

        if (frm.doc.status === "Rejected") {
            return;
        }

        frm.add_custom_button(__("Create Supplier"), function () {
            frappe.confirm(
    __("Are you sure you want to create the Supplier?"),
    function () {
        frappe.call({
            method: "chithiyan.chithiyan.doctype.vendor_registration.vendor_registration.create_supplier",
            args: {
                vendor_registration: frm.doc.name
            },
            freeze: true,
            freeze_message: __("Creating Supplier..."),

            callback: function (r) {
                if (r.message && r.message.success) {
                    frappe.show_alert({
                        message: __("Supplier created successfully."),
                        indicator: "green"
                    });

                    frm.reload_doc();
                }
            }
        });
    }
);
        });
    }
});