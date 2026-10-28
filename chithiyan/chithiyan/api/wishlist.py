import frappe

from chithiyan.chithiyan.api.quotations import (
    WISHLIST,
    add_item,
    get_customer,
    get_open_doc,
    remove_item,
    serialize,
)


@frappe.whitelist()
def add_to_wishlist(item_code, qty=1):
    customer = get_customer()
    doc, created = add_item(customer, WISHLIST, item_code, qty)
    return {"name": doc.name, "created": created}


@frappe.whitelist()
def remove_from_wishlist(item_code):
    customer = get_customer()
    before = get_open_doc(customer, WISHLIST)
    if not before or not any(i.item_code == item_code for i in before.items):
        return {"deleted": False}

    remove_item(customer, WISHLIST, item_code)
    return {"deleted": True, "name": before.name}


@frappe.whitelist()
def get_wishlist():
    customer = get_customer()
    return serialize(get_open_doc(customer, WISHLIST))