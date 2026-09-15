import frappe
from frappe import _


def _get_item_group_tree(parent_item_group):
    """
    Return parent Item Group and all its child Item Groups.
    """

    parent = frappe.db.get_value(
        "Item Group",
        parent_item_group,
        ["name", "lft", "rgt"],
        as_dict=True,
    )

    if not parent:
        frappe.throw(
            _("Item Group {0} does not exist.").format(parent_item_group)
        )

    groups = frappe.get_all(
        "Item Group",
        filters={
            "lft": [">=", parent.lft],
            "rgt": ["<=", parent.rgt],
        },
        fields=["name"],
        order_by="lft asc",
    )

    return [group.name for group in groups]


@frappe.whitelist(allow_guest=True)
def get_sub_item_groups(parent_item_group=None):
    """
    Get direct child Item Groups of Cakes/Bouquets.
    """

    if not parent_item_group:
        frappe.throw(_("Parent Item Group is required."))

    if not frappe.db.exists("Item Group", parent_item_group):
        frappe.throw(
            _("Item Group {0} does not exist.").format(parent_item_group)
        )

    sub_item_groups = frappe.get_all(
        "Item Group",
        filters={
            "parent_item_group": parent_item_group,
            "is_group": 0,
        },
        fields=[
            "name",
            "parent_item_group",
            "is_group",
        ],
        order_by="lft asc",
    )

    return sub_item_groups


@frappe.whitelist(allow_guest=True)
def get_category_products(
    parent_item_group=None,
    item_group=None,
    price_list="Standard Selling",
):
    """
    Fetch products dynamically from ERPNext Item.

    parent_item_group:
        Cakes / Bouquets

    item_group:
        Selected child Item Group.
        If empty, all items under parent_item_group are returned.

    price_list:
        Standard Selling by default.
    """

    if not parent_item_group:
        frappe.throw(_("Parent Item Group is required."))

    if not frappe.db.exists("Item Group", parent_item_group):
        frappe.throw(
            _("Item Group {0} does not exist.").format(parent_item_group)
        )

    # ---------------------------------------------------------
    # GET VALID ITEM GROUPS
    # ---------------------------------------------------------

    parent_groups = _get_item_group_tree(parent_item_group)

    # ---------------------------------------------------------
    # SELECTED SUB CATEGORY
    # ---------------------------------------------------------

    if item_group and item_group != "All":

        if item_group not in parent_groups:
            frappe.throw(
                _(
                    "Item Group {0} does not belong to {1}."
                ).format(item_group, parent_item_group)
            )

        selected_groups = _get_item_group_tree(item_group)

    else:
        selected_groups = parent_groups

    # ---------------------------------------------------------
    # FETCH ITEMS
    # ---------------------------------------------------------

    items = frappe.get_all(
        "Item",
        filters={
            "item_group": ["in", selected_groups],
            "disabled": 0,
            "is_sales_item": 1,
        },
        fields=[
            "name",
            "item_code",
            "item_name",
            "description",
            "image",
            "item_group",
            "stock_uom",
        ],
        order_by="modified desc",
    )

    if not items:
        return []

    # ---------------------------------------------------------
    # ITEM PRICES
    # ---------------------------------------------------------

    item_codes = [item.item_code for item in items]

    prices = frappe.get_all(
        "Item Price",
        filters={
            "item_code": ["in", item_codes],
            "price_list": price_list,
            "selling": 1,
            "currency": ["is", "set"],
        },
        fields=[
            "item_code",
            "price_list",
            "price_list_rate",
            "currency",
            "uom",
        ],
        order_by="valid_from desc, modified desc",
    )

    # ---------------------------------------------------------
    # CREATE PRICE MAP
    # ---------------------------------------------------------

    price_map = {}

    for price in prices:

        # First price for an item wins because
        # results are ordered latest first.
        if price.item_code not in price_map:
            price_map[price.item_code] = price

    # ---------------------------------------------------------
    # FINAL PRODUCT RESPONSE
    # ---------------------------------------------------------

    result = []

    for item in items:

        item_price = price_map.get(item.item_code)

        price = 0
        currency = "INR"

        if item_price:
            price = item_price.price_list_rate or 0
            currency = item_price.currency or "INR"

        result.append(
            {
                "item_code": item.item_code,
                "item_name": item.item_name or item.item_code,
                "description": item.description or "",
                "image": item.image or "",
                "item_group": item.item_group,
                "stock_uom": item.stock_uom or "",
                "price": price,
                "currency": currency,
            }
        )

    return result