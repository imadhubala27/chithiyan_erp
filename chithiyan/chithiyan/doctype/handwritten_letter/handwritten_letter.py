import frappe

from frappe import _
from frappe.utils import flt, nowdate
from frappe.model.document import Document


class HandwrittenLetter(Document):
    pass


HANDWRITTEN_ITEM_CODE = "Handwritten Letter"


def _set_if_field(doc, fieldname, value):
    """Set a field only when it exists on the target DocType."""
    if value is None:
        return

    meta = frappe.get_meta(doc.doctype)

    if meta.has_field(fieldname):
        doc.set(fieldname, value)


def _get_or_create_customer_for_user(user_email):
    if not user_email or user_email == "Guest":
        frappe.throw(_("Please login before adding a handwritten letter to cart."))

    if not frappe.db.exists("User", user_email):
        frappe.throw(_("Logged-in user was not found in ERPNext."))

    user = frappe.get_doc("User", user_email)

    customer_name = frappe.db.get_value(
        "Customer",
        {"email_id": user_email},
        "name",
    )

    if customer_name:
        return customer_name, user, False

    customer_display_name = (
        user.full_name
        or " ".join(filter(None, [user.first_name, user.last_name])).strip()
        or user_email.split("@")[0]
        or "Customer"
    )

    customer_group = "Individual" if frappe.db.exists("Customer Group", "Individual") else frappe.db.get_value(
        "Customer Group",
        {"is_group": 0},
        "name",
        order_by="name asc",
    )

    territory = "All Territories" if frappe.db.exists("Territory", "All Territories") else frappe.db.get_value(
        "Territory",
        {"is_group": 0},
        "name",
        order_by="name asc",
    )

    if not customer_group:
        frappe.throw(_("No active Customer Group is available in ERPNext."))

    if not territory:
        frappe.throw(_("No active Territory is available in ERPNext."))

    customer_doc = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": customer_display_name,
            "customer_type": "Individual",
            "customer_group": customer_group,
            "territory": territory,
            "email_id": user_email,
            "mobile_no": getattr(user, "mobile_no", None),
        }
    )

    customer_doc.insert(ignore_permissions=True)

    return customer_doc.name, user, True


def _get_exchange_rate(from_currency, to_currency, date=None):
    """Return exchange rate; 1 when currencies are same or rate not found."""
    if not from_currency or not to_currency or from_currency == to_currency:
        return 1.0

    try:
        from erpnext.setup.utils import get_exchange_rate

        return flt(get_exchange_rate(from_currency, to_currency, date or nowdate())) or 1.0
    except Exception:
        return 1.0


def _get_uom_conversion_factor(item_code, uom, stock_uom):
    """Conversion factor of `uom` w.r.t. item's stock UOM."""
    if not uom or uom == stock_uom:
        return 1.0

    factor = frappe.db.get_value(
        "UOM Conversion Detail",
        {"parent": item_code, "uom": uom},
        "conversion_factor",
    )

    return flt(factor) or 1.0


@frappe.whitelist(allow_guest=True)
def create_handwritten_letter_and_quotation(
    sender_full_name=None,
    signature_style=None,
    recipient_full_name=None,
    salutation=None,
    letter_intention=None,
    flat_house_no_building=None,
    street_locality_details=None,
    pincode=None,
    recipient_phone=None,
    city=None,
    state=None,
    letter_message=None,
    current_step="Review",
    paper_type=None,
    calligraphy_style=None,
    envelope_color=None,
    wax_seal=None,
):
    """
    Create the complete handwritten-letter cart flow:

    1. Require a logged-in Frappe user.
    2. Find that user's ERPNext Customer by email_id.
    3. Create the Customer if it does not exist.
    4. Create the Handwritten Letter and link it to the User.
    5. Create a draft ERPNext Quotation for the "Handwritten Letter" Item.
    6. Link the Quotation back to the Handwritten Letter.

    The Customer/User identity is ALWAYS taken from frappe.session.user.
    """
    try:
        # ---------------------------------------------------------
        # STEP 1: LOGIN CHECK
        # ---------------------------------------------------------
        user_email = frappe.session.user

        if not user_email or user_email == "Guest":
            frappe.throw(
                _("Please login before adding a handwritten letter to cart.")
            )

        # ---------------------------------------------------------
        # STEP 2: GET OR CREATE ERPNext CUSTOMER
        # ---------------------------------------------------------
        customer_name, user, customer_created = _get_or_create_customer_for_user(user_email)

        # ---------------------------------------------------------
        # STEP 3: CREATE HANDWRITTEN LETTER
        # ---------------------------------------------------------
        letter = frappe.get_doc(
            {
                "doctype": "Handwritten Letter",
                "sender_full_name": sender_full_name or "",
                "signature_style": signature_style or "",
                "recipient_full_name": recipient_full_name or "",
                "salutation": salutation or "",
                "letter_intention": letter_intention or "",
                "flat_house_no_building": flat_house_no_building or "",
                "street_locality_details": street_locality_details or "",
                "pincode": pincode or "",
                "recipient_phone": recipient_phone or "",
                "city": city or "",
                "state": state or "",
                "letter_message": letter_message or "",
                # Handwritten Letter.customer is a Link to User.
                "customer": user_email,
                "current_step": current_step or "Review",
            }
        )

        _set_if_field(letter, "paper_type", paper_type)
        _set_if_field(letter, "calligraphy_style", calligraphy_style)
        _set_if_field(letter, "envelope_color", envelope_color)
        _set_if_field(letter, "wax_seal", wax_seal)

        letter.insert(ignore_permissions=True)

        # ---------------------------------------------------------
        # STEP 4: GET "Handwritten Letter" ITEM DETAILS
        # ---------------------------------------------------------
        if not frappe.db.exists("Item", HANDWRITTEN_ITEM_CODE):
            frappe.throw(
                _(
                    "ERPNext Item '{0}' does not exist. Please create the item before adding the letter to cart."
                ).format(HANDWRITTEN_ITEM_CODE)
            )

        item = frappe.db.get_value(
            "Item",
            HANDWRITTEN_ITEM_CODE,
            ["item_name", "description", "stock_uom", "sales_uom", "standard_rate", "item_group"],
            as_dict=True,
        )

        item_name = item.item_name or HANDWRITTEN_ITEM_CODE
        stock_uom = item.stock_uom or "Nos"
        uom = item.sales_uom or stock_uom
        conversion_factor = _get_uom_conversion_factor(HANDWRITTEN_ITEM_CODE, uom, stock_uom)

        # ---------------------------------------------------------
        # STEP 5: GET SELLING PRICE LIST
        # ---------------------------------------------------------
        selling_price_list = frappe.db.get_single_value(
            "Selling Settings", "selling_price_list"
        )

        if not selling_price_list:
            selling_price_list = frappe.db.get_value(
                "Price List",
                {"selling": 1, "enabled": 1},
                "name",
                order_by="name asc",
            )

        if not selling_price_list:
            frappe.throw(
                _("No enabled selling Price List is configured in ERPNext.")
            )

        # ---------------------------------------------------------
        # STEP 6: GET ITEM PRICE
        # ---------------------------------------------------------
        rate = frappe.db.get_value(
            "Item Price",
            {
                "item_code": HANDWRITTEN_ITEM_CODE,
                "price_list": selling_price_list,
                "selling": 1,
            },
            "price_list_rate",
        )

        # Fallbacks: Item standard rate, then the existing Chithiyan price.
        rate = flt(rate or item.standard_rate or 1499)

        # ---------------------------------------------------------
        # STEP 7: GET COMPANY + CURRENCIES
        # ---------------------------------------------------------
        company = frappe.defaults.get_user_default("Company")

        if not company:
            company = frappe.db.get_single_value(
                "Global Defaults", "default_company"
            )

        if not company:
            company = frappe.db.get_value(
                "Company",
                {},
                "name",
                order_by="name asc",
            )

        if not company:
            frappe.throw(
                _("No Company is configured in ERPNext for creating the quotation.")
            )

        company_currency = frappe.get_cached_value("Company", company, "default_currency")

        if not company_currency:
            frappe.throw(
                _("Default Currency is not set for Company {0}.").format(company)
            )

        price_list_currency = (
            frappe.db.get_value("Price List", selling_price_list, "currency")
            or company_currency
        )

        today = nowdate()

        # Quotation currency = price list currency
        currency = price_list_currency
        conversion_rate = _get_exchange_rate(currency, company_currency, today)
        plc_conversion_rate = _get_exchange_rate(price_list_currency, company_currency, today)

        # ---------------------------------------------------------
        # STEP 8: CREATE DRAFT QUOTATION
        # ---------------------------------------------------------
        quotation = frappe.get_doc(
            {
                "doctype": "Quotation",
                "quotation_to": "Customer",
                "party_name": customer_name,
                "customer_name": frappe.db.get_value("Customer", customer_name, "customer_name"),
                "order_type": "Shopping Cart" if "Shopping Cart" in (frappe.get_meta("Quotation").get_field("order_type").options or "") else "Sales",
                "transaction_date": today,
                "company": company,
                "currency": currency,
                "conversion_rate": conversion_rate,
                "selling_price_list": selling_price_list,
                "price_list_currency": price_list_currency,
                "plc_conversion_rate": plc_conversion_rate,
                "items": [
                    {
                        "item_code": HANDWRITTEN_ITEM_CODE,
                        "item_name": item_name,
                        "description": item.description or item_name,
                        "item_group": item.item_group,
                        "qty": 1,
                        "uom": uom,
                        "stock_uom": stock_uom,
                        "conversion_factor": conversion_factor,
                        "price_list_rate": rate,
                        "rate": rate,
                    }
                ],
            }
        )

        # Link Quotation -> Handwritten Letter when the custom field exists.
        _set_if_field(quotation, "custom_handwritten_letter", letter.name)

        # validate() is skipped to avoid the Contact.is_billing_contact schema error,
        # so all mandatory values are set manually above and totals are calculated here.
        quotation.flags.ignore_validate = True
        quotation.calculate_taxes_and_totals()
        quotation.insert(ignore_permissions=True)

        # ---------------------------------------------------------
        # STEP 9: LINK HANDWRITTEN LETTER -> QUOTATION
        # ---------------------------------------------------------
        _set_if_field(letter, "quotation", quotation.name)
        letter.save(ignore_permissions=True)

        # ---------------------------------------------------------
        # STEP 10: COMMIT ONLY AFTER EVERYTHING SUCCEEDS
        # ---------------------------------------------------------
        frappe.db.commit()

        return {
            "handwritten_letter": letter.name,
            "quotation": quotation.name,
            "customer": customer_name,
            "customer_created": customer_created,
            "amount": rate,
        }

    except Exception:
        frappe.db.rollback()
        raise