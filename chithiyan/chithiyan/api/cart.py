import frappe

from chithiyan.chithiyan.api.quotations import (
    CART,
    add_item,
    get_customer,
    get_open_doc,
    remove_item,
    set_qty,
)


@frappe.whitelist()
def get_cart():
    customer = get_customer()
    doc = get_open_doc(customer, CART)
    if not doc:
        return []

    return frappe.db.sql(
        """
        SELECT
            qi.item_code,
            qi.item_name,
            qi.qty,
            qi.rate,
            COALESCE(NULLIF(qi.image, ''), i.image) AS image
        FROM `tabQuotation Item` qi
        LEFT JOIN `tabItem` i ON i.name = qi.item_code
        WHERE qi.parent = %s
        ORDER BY qi.idx ASC
        """,
        (doc.name,),
        as_dict=True,
    )


@frappe.whitelist()
def add_to_cart(item_code, qty=1):
    customer = get_customer()
    doc, created = add_item(customer, CART, item_code, qty, accumulate=True)

    row = next((i for i in doc.items if i.item_code == item_code), None)
    return {
        "name": doc.name,
        "created": created,
        "qty": float(row.qty) if row else 0,
    }


@frappe.whitelist()
def set_cart_qty(item_code, qty):
    customer = get_customer()
    qty = float(qty)

    before = get_open_doc(customer, CART)
    if not before or not any(i.item_code == item_code for i in before.items):
        return {"updated": False}

    if qty <= 0:
        doc = remove_item(customer, CART, item_code)
        return {"deleted": True, "name": before.name, "quotation_deleted": doc is None}

    doc = set_qty(customer, CART, item_code, qty)
    return {"updated": True, "name": doc.name, "qty": qty}


@frappe.whitelist()
def remove_from_cart(item_code):
    customer = get_customer()

    before = get_open_doc(customer, CART)
    if not before or not any(i.item_code == item_code for i in before.items):
        return {"deleted": False}

    remove_item(customer, CART, item_code)
    return {"deleted": True, "name": before.name}