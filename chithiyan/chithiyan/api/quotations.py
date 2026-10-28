import hashlib
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate
from frappe.utils.synchronization import filelock

WISHLIST = "Wishlist"
CART = "Shopping Cart"
MAX_QTY = 100

_KIND_MAP = {
    "wishlist": WISHLIST,
    "cart": CART,
    "shopping cart": CART,
}


def resolve_order_type(kind):
    return _KIND_MAP.get(str(kind or "").strip().lower(), kind)


def get_item_code(cart_item_id):
    """Map a frontend item id to an ERPNext Item Code. Change here if they differ."""
    return str(cart_item_id or "").strip()



def get_customer():
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please login first"), frappe.PermissionError)

    customer = frappe.db.get_value(
        "Portal User", {"user": user, "parenttype": "Customer"}, "parent"
    )

    if not customer:
        contact = frappe.db.get_value(
            "Contact Email", {"email_id": user, "parenttype": "Contact"}, "parent"
        )
        if contact:
            customer = frappe.db.get_value(
                "Dynamic Link",
                {"parent": contact, "parenttype": "Contact", "link_doctype": "Customer"},
                "link_name",
            )

    if not customer:
        frappe.throw(_("No Customer linked with this user"))

    return customer


def _get_contact(user, customer):
    candidates = []

    by_user = frappe.db.get_value("Contact", {"user": user}, "name")
    if by_user:
        candidates.append(by_user)

    candidates += frappe.get_all(
        "Contact Email",
        filters={"email_id": user, "parenttype": "Contact"},
        pluck="parent",
    )

    for contact in candidates:
        linked = frappe.db.exists(
            "Dynamic Link",
            {
                "parent": contact,
                "parenttype": "Contact",
                "link_doctype": "Customer",
                "link_name": customer,
            },
        )
        if linked:
            return contact

    return None


@contextmanager
def _lock(customer, order_type):
    """Ek customer + list type pe ek time me ek hi write (duplicate quotation rokne ke liye)."""
    key = hashlib.md5(f"{customer}|{order_type}".encode()).hexdigest()
    with filelock(f"quotation_{key}", timeout=30):
        yield


def get_open_doc(customer, order_type):
    """Customer ki single draft quotation (wishlist ya cart)."""
    name = frappe.db.get_value(
        "Quotation",
        {
            "quotation_to": "Customer",
            "party_name": customer,
            "order_type": order_type,
            "docstatus": 0,
        },
        "name",
        order_by="modified desc",
    )
    return frappe.get_doc("Quotation", name) if name else None


def save_doc(doc):
    doc.set_missing_lead_customer_details = lambda *args, **kwargs: None
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    return doc


def _row(item_code, qty, price=None):
    if not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item not found: {0}").format(item_code))

    row = {"item_code": item_code, "qty": min(max(flt(qty) or 1, 1), MAX_QTY)}

    rate = flt(frappe.db.get_value("Item", item_code, "standard_rate"))
    if rate <= 0:
        rate = flt(price)
    if rate > 0:
        row["rate"] = rate
    return row


def _new_doc(customer, order_type, rows):
    doc = frappe.get_doc(
        {
            "doctype": "Quotation",
            "quotation_to": "Customer",
            "party_name": customer,
            "contact_person": _get_contact(frappe.session.user, customer),
            "company": frappe.db.get_single_value("Global Defaults", "default_company"),
            "order_type": order_type,
            "selling_price_list": frappe.db.get_single_value(
                "Selling Settings", "selling_price_list"
            )
            or "Standard Selling",
            "transaction_date": nowdate(),
            "items": rows,
        }
    )
    doc.set_missing_lead_customer_details = lambda *args, **kwargs: None
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    return doc


def _remove_item(customer, order_type, item_code):
    doc = get_open_doc(customer, order_type)
    if not doc:
        return None

    rows = [i for i in doc.items if i.item_code == item_code]
    if not rows:
        return doc

    for row in rows:
        doc.remove(row)

    if not doc.items:
        frappe.delete_doc("Quotation", doc.name, ignore_permissions=True, force=True)
        return None

    return save_doc(doc)


def add_item(customer, order_type, item_code, qty=1, accumulate=False):
    """Item add karo. Returns (doc, created)."""
    with _lock(customer, order_type):
        doc = get_open_doc(customer, order_type)
        row = _row(item_code, qty)

        if not doc:
            return _new_doc(customer, order_type, [row]), True

        existing = next((i for i in doc.items if i.item_code == item_code), None)
        if existing:
            if accumulate:
                existing.qty = min(flt(existing.qty) + row["qty"], MAX_QTY)
                save_doc(doc)
            return doc, False

        doc.append("items", row)
        save_doc(doc)
        return doc, False


def set_qty(customer, order_type, item_code, qty):
    with _lock(customer, order_type):
        doc = get_open_doc(customer, order_type)
        if not doc:
            return None

        if flt(qty) <= 0:
            return _remove_item(customer, order_type, item_code)

        for item in doc.items:
            if item.item_code == item_code:
                item.qty = min(flt(qty), MAX_QTY)
        return save_doc(doc)


def remove_item(customer, order_type, item_code):
    with _lock(customer, order_type):
        return _remove_item(customer, order_type, item_code)


def replace_items(customer, order_type, items):
    """Quotation ko `items` ke bilkul barabar bana do: [{item_code, qty, price?}]."""
    with _lock(customer, order_type):
        merged = {}
        for item in items or []:
            code = get_item_code(item.get("item_code") or item.get("id"))
            if not code:
                continue
            row = _row(code, item.get("qty") or 1, item.get("price"))
            if code in merged:
                row["qty"] = min(merged[code]["qty"] + row["qty"], MAX_QTY)
            merged[code] = row

        doc = get_open_doc(customer, order_type)

        if not merged:
            if doc:
                frappe.delete_doc("Quotation", doc.name, ignore_permissions=True, force=True)
            return None

        if not doc:
            return _new_doc(customer, order_type, list(merged.values()))

        doc.set("items", [])
        for row in merged.values():
            doc.append("items", row)
        return save_doc(doc)


def sync_quotation(customer, kind, items):
    """
    Checkout se pehle quotation ko checkout items ke barabar karo.
    `kind` = "Cart" / "Shopping Cart" / "Wishlist".
    Returns (quotation_doc_or_None, skipped_item_codes).
    """
    order_type = resolve_order_type(kind)

    valid, skipped = [], []
    for item in items or []:
        code = get_item_code(item.get("id") or item.get("item_code"))
        if not code:
            continue
        if not frappe.db.exists("Item", code):
            skipped.append(code)
            continue

        qty = cint(item.get("qty"))
        if qty < 1 or qty > MAX_QTY:
            frappe.throw(_("Invalid quantity for {0}").format(code))

        valid.append({"item_code": code, "qty": qty, "price": item.get("price")})

    if skipped:
        return None, skipped

    return replace_items(customer, order_type, valid), []


def serialize(doc):
    if not doc:
        return {"name": None, "items": []}
    return {
        "name": doc.name,
        "items": [
            {"item_code": i.item_code, "qty": cint(i.qty), "rate": flt(i.rate)}
            for i in doc.items
        ],
    }