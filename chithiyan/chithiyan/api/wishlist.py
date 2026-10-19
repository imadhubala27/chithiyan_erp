import frappe
from frappe import _


def _get_customer():
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


def _find_wishlist_quotation(customer, item_code):
    rows = frappe.db.sql(
        """
        SELECT q.name
        FROM `tabQuotation` q
        INNER JOIN `tabQuotation Item` qi ON qi.parent = q.name
        WHERE q.docstatus = 0
          AND q.order_type = 'Wishlist'
          AND q.quotation_to = 'Customer'
          AND q.party_name = %s
          AND qi.item_code = %s
        LIMIT 1
        """,
        (customer, item_code),
    )
    return rows[0][0] if rows else None


@frappe.whitelist()
def add_to_wishlist(item_code, qty=1):
    customer = _get_customer()

    existing = _find_wishlist_quotation(customer, item_code)
    if existing:
        return {"name": existing, "created": False}

    doc = frappe.get_doc(
        {
            "doctype": "Quotation",
            "quotation_to": "Customer",
            "party_name": customer,
            "contact_person": _get_contact(frappe.session.user, customer),
            "order_type": "Wishlist",
            "transaction_date": frappe.utils.nowdate(),
            "items": [{"item_code": item_code, "qty": float(qty)}],
        }
    )
    doc.set_missing_lead_customer_details = lambda *args, **kwargs: None
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)

    return {"name": doc.name, "created": True}


@frappe.whitelist()
def remove_from_wishlist(item_code):
    customer = _get_customer()

    name = _find_wishlist_quotation(customer, item_code)
    if not name:
        return {"deleted": False}

    frappe.delete_doc("Quotation", name, ignore_permissions=True, force=True)

    return {"deleted": True, "name": name}