import frappe
from frappe.utils import cint

PRICE_LIST = "Standard Selling"


def _clamp_limit(limit, default):
    limit = cint(limit) or default
    return max(1, min(limit, 20))


def _build_products(item_codes):
    """item_codes ke order me hi products return karta hai."""
    if not item_codes:
        return []

    items = frappe.get_all(
        "Item",
        filters={"name": ["in", item_codes]},
        fields=["name", "item_name", "image", "item_group", "description"],
    )
    by_code = {i.name: i for i in items}

    prices = frappe.get_all(
        "Item Price",
        filters={
            "item_code": ["in", item_codes],
            "price_list": PRICE_LIST,
            "selling": 1,
        },
        fields=["item_code", "price_list_rate"],
        order_by="modified desc",
    )
    price_map = {}
    for p in prices:
        price_map.setdefault(p.item_code, float(p.price_list_rate or 0))

    result = []
    for code in item_codes:
        item = by_code.get(code)
        if not item:
            continue
        result.append(
            {
                "item_code": item.name,
                "item_name": item.item_name,
                "image": item.image,
                "item_group": item.item_group,
                "description": item.description,
                "price": price_map.get(code, 0),
            }
        )
    return result


@frappe.whitelist(allow_guest=True)
def get_best_sellers(limit=4):
    """Sabse zyada Delivery Notes wale items (cancelled DN count nahi hote)."""
    limit = _clamp_limit(limit, 4)

    rows = frappe.db.sql(
        """
        SELECT dni.item_code, COUNT(DISTINCT dni.parent) AS dn_count
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        INNER JOIN `tabItem` i ON i.name = dni.item_code
        WHERE dn.docstatus != 2
          AND i.disabled = 0
          AND i.is_sales_item = 1
        GROUP BY dni.item_code
        ORDER BY dn_count DESC, dni.item_code ASC
        LIMIT %s
        """,
        (limit,),
    )

    return _build_products([r[0] for r in rows])


@frappe.whitelist(allow_guest=True)
def get_new_arrivals(limit=4):
    """Sabse latest bane hue items."""
    limit = _clamp_limit(limit, 4)

    codes = frappe.get_all(
        "Item",
        filters={"disabled": 0, "is_sales_item": 1},
        order_by="creation desc",
        limit_page_length=limit,
        pluck="name",
    )

    return _build_products(codes)

@frappe.whitelist(allow_guest=True)
def get_related_products(item_code, limit=4):
    """Parent Item Group (aur uske saare child groups) ke doosre items."""
    limit = _clamp_limit(limit, 4)

    item_group = frappe.db.get_value("Item", item_code, "item_group")
    if not item_group:
        return []

    parent_group = frappe.db.get_value("Item Group", item_group, "parent_item_group")

    # Parent na ho ya root ("All Item Groups") ho to item ka apna group use karo
    if not parent_group or parent_group == "All Item Groups":
        parent_group = item_group

    # Parent ke andar ke saare groups (child + nested) nested-set se
    lft, rgt = frappe.db.get_value("Item Group", parent_group, ["lft", "rgt"])
    groups = frappe.get_all(
        "Item Group",
        filters={"lft": [">=", lft], "rgt": ["<=", rgt]},
        pluck="name",
    )

    codes = frappe.get_all(
        "Item",
        filters={
            "item_group": ["in", groups],
            "name": ["!=", item_code],
            "disabled": 0,
            "is_sales_item": 1,
        },
        order_by="creation desc",
        limit_page_length=limit,
        pluck="name",
    )

    return _build_products(codes)