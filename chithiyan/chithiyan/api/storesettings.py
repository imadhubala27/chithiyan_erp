import frappe
from frappe import _
from frappe.utils.password import check_password, update_password


# =========================================================
# CURRENT USER
# =========================================================

def _get_current_user():
    user = frappe.session.user

    if not user or user == "Guest":
        frappe.throw(
            _("Please login first."),
            frappe.AuthenticationError,
        )

    return user


# =========================================================
# NAME HELPERS
# =========================================================

def _split_name(full_name):
    full_name = (full_name or "").strip()

    if not full_name:
        return "", ""

    parts = full_name.split()

    first_name = parts[0]

    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    return first_name, last_name


# =========================================================
# CONTACT
# =========================================================

def _get_user_contact(user):
    """
    Find Contact connected with current ERPNext User.
    """

    # 1. Direct user field
    contact_name = frappe.db.get_value(
        "Contact",
        {"user": user},
        "name",
    )

    if contact_name:
        return frappe.get_doc(
            "Contact",
            contact_name,
        )

    # 2. Email field
    contact_name = frappe.db.get_value(
        "Contact",
        {"email_id": user},
        "name",
    )

    if contact_name:
        return frappe.get_doc(
            "Contact",
            contact_name,
        )

    # 3. Contact Email child table
    contact_name = frappe.db.sql(
        """
        SELECT parent
        FROM `tabContact Email`
        WHERE email_id = %s
        AND parenttype = 'Contact'
        LIMIT 1
        """,
        user,
    )

    if contact_name:
        return frappe.get_doc(
            "Contact",
            contact_name[0][0],
        )

    return None


# =========================================================
# CREATE CONTACT
# =========================================================

def _create_user_contact(
    user,
    full_name,
    mobile_no=None,
):
    first_name, last_name = _split_name(
        full_name
    )

    contact = frappe.get_doc(
        {
            "doctype": "Contact",
            "first_name": first_name,
            "last_name": last_name,
            "email_id": user,
            "mobile_no": mobile_no or "",
            "user": user,
        }
    )

    contact.insert(
        ignore_permissions=True
    )

    return contact


# =========================================================
# ADDRESS LINK CHECK
# =========================================================

def _address_belongs_to_user(
    address_id,
    user,
):
    return frappe.db.exists(
        "Dynamic Link",
        {
            "parent": address_id,
            "parenttype": "Address",
            "link_doctype": "User",
            "link_name": user,
        },
    )


# =========================================================
# GET USER ADDRESSES
# =========================================================

def _get_user_addresses(user):
    """
    Get all Address records linked with current User.
    """

    rows = frappe.db.sql(
        """
        SELECT DISTINCT
            dl.parent AS name
        FROM `tabDynamic Link` dl
        INNER JOIN `tabAddress` a
            ON a.name = dl.parent
        WHERE dl.parenttype = 'Address'
        AND dl.link_doctype = 'User'
        AND dl.link_name = %s
        ORDER BY a.creation ASC
        """,
        user,
        as_dict=True,
    )

    addresses = []

    for row in rows:
        address = frappe.get_doc(
            "Address",
            row.name,
        )

        address_type = (
            address.address_type
            or "Shipping"
        )

        if address_type == "Billing":
            label = "Preferred Billing Address"
        else:
            label = "Preferred Shipping Address"

        addresses.append(
            {
                "id": address.name,
                "name": address.name,

                "label": label,

                # address_title is used for recipient name
                "fullName": (
                    address.address_title
                    or ""
                ),

                "phone": (
                    address.phone
                    or ""
                ),

                "line1": (
                    address.address_line1
                    or ""
                ),

                "line2": (
                    address.address_line2
                    or ""
                ),

                "city": (
                    address.city
                    or ""
                ),

                "state": (
                    address.state
                    or ""
                ),

                "pincode": (
                    address.pincode
                    or ""
                ),

                "country": (
                    address.country
                    or ""
                ),

                "addressType": address_type,

                "isDefault": bool(
                    address.is_primary_address
                ),
            }
        )

    return addresses


# =========================================================
# GET SETTINGS
# =========================================================

@frappe.whitelist(methods=["GET"])
def get_settings():
    user = _get_current_user()

    user_doc = frappe.get_doc(
        "User",
        user,
    )

    contact = _get_user_contact(
        user
    )

    addresses = _get_user_addresses(
        user
    )

    return {
        "user": {
            "email": user_doc.email,

            "name": (
                user_doc.full_name
                or user_doc.first_name
                or user_doc.email
            ),

            "first_name": (
                user_doc.first_name
                or ""
            ),

            "last_name": (
                user_doc.last_name
                or ""
            ),

            "mobile_no": (
                user_doc.mobile_no
                or (
                    contact.mobile_no
                    if contact
                    else ""
                )
                or ""
            ),
        },

        "contact": (
            {
                "name": contact.name,
                "full_name": contact.full_name,
                "email_id": contact.email_id,
                "mobile_no": contact.mobile_no,
            }
            if contact
            else None
        ),

        "addresses": addresses,
    }


# =========================================================
# UPDATE ACCOUNT
# =========================================================

@frappe.whitelist(methods=["POST"])
def update_account(
    full_name=None,
    mobile_no=None,
):
    user = _get_current_user()

    full_name = (
        full_name or ""
    ).strip()

    mobile_no = (
        mobile_no or ""
    ).strip()

    if not full_name:
        frappe.throw(
            _("Full name is required.")
        )

    first_name, last_name = _split_name(
        full_name
    )

    # -----------------------------------------------------
    # USER
    # -----------------------------------------------------

    user_doc = frappe.get_doc(
        "User",
        user,
    )

    user_doc.first_name = first_name
    user_doc.last_name = last_name
    user_doc.mobile_no = mobile_no

    user_doc.save(
        ignore_permissions=True
    )

    # -----------------------------------------------------
    # CONTACT
    # -----------------------------------------------------

    contact = _get_user_contact(
        user
    )

    if not contact:
        contact = _create_user_contact(
            user=user,
            full_name=full_name,
            mobile_no=mobile_no,
        )

    else:
        contact.first_name = first_name
        contact.last_name = last_name
        contact.email_id = user
        contact.mobile_no = mobile_no
        contact.user = user

        contact.save(
            ignore_permissions=True
        )

    frappe.db.commit()

    return {
        "success": True,

        "message":
            "Account details updated successfully.",

        "user": {
            "email": user_doc.email,

            "name": (
                user_doc.full_name
                or full_name
            ),

            "mobile_no": mobile_no,
        },

        "contact": {
            "name": contact.name,
            "full_name": contact.full_name,
            "email_id": contact.email_id,
            "mobile_no": contact.mobile_no,
        },
    }


# =========================================================
# CHANGE PASSWORD
# =========================================================

@frappe.whitelist(methods=["POST"])
def change_password(
    current_password=None,
    new_password=None,
):
    user = _get_current_user()

    current_password = (
        current_password or ""
    )

    new_password = (
        new_password or ""
    )

    if not current_password:
        frappe.throw(
            _("Current password is required.")
        )

    if not new_password:
        frappe.throw(
            _("New password is required.")
        )

    if len(new_password) < 6:
        frappe.throw(
            _(
                "New password must be at least 6 characters."
            )
        )

    if current_password == new_password:
        frappe.throw(
            _(
                "New password must be different from the current password."
            )
        )

    # -----------------------------------------------------
    # CHECK OLD PASSWORD
    # -----------------------------------------------------

    try:
        check_password(
            user,
            current_password,
        )

    except frappe.AuthenticationError:
        frappe.throw(
            _("Current password is incorrect."),
            frappe.AuthenticationError,
        )

    # -----------------------------------------------------
    # UPDATE PASSWORD
    # -----------------------------------------------------

    update_password(
        user=user,
        pwd=new_password,
        logout_all_sessions=False,
    )

    frappe.db.commit()

    return {
        "success": True,
        "message":
            "Password updated successfully.",
    }


# =========================================================
# SAVE ADDRESS
# =========================================================

@frappe.whitelist(methods=["POST"])
def save_address(
    address_id=None,
    full_name=None,
    phone=None,
    line1=None,
    line2=None,
    city=None,
    state=None,
    pincode=None,
    country=None,
    address_type=None,
    is_default=0,
):
    user = _get_current_user()

    # -----------------------------------------------------
    # CLEAN VALUES
    # -----------------------------------------------------

    full_name = (
        full_name or ""
    ).strip()

    phone = (
        phone or ""
    ).strip()

    line1 = (
        line1 or ""
    ).strip()

    line2 = (
        line2 or ""
    ).strip()

    city = (
        city or ""
    ).strip()

    state = (
        state or ""
    ).strip()

    pincode = (
        pincode or ""
    ).strip()

    country = (
        country or ""
    ).strip()

    address_type = (
        address_type or "Shipping"
    ).strip()

    try:
        is_default = int(
            is_default or 0
        )
    except Exception:
        is_default = 0

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if not full_name:
        frappe.throw(
            _("Full name is required.")
        )

    if not phone:
        frappe.throw(
            _("Phone is required.")
        )

    if not line1:
        frappe.throw(
            _("Address line 1 is required.")
        )

    if not city:
        frappe.throw(
            _("City is required.")
        )

    if not state:
        frappe.throw(
            _("State is required.")
        )

    if not pincode:
        frappe.throw(
            _("PIN / ZIP is required.")
        )

    if not country:
        frappe.throw(
            _("Country is required.")
        )

    if address_type not in (
        "Billing",
        "Shipping",
    ):
        frappe.throw(
            _(
                "Address type must be Billing or Shipping."
            )
        )

    # -----------------------------------------------------
    # EXISTING / NEW ADDRESS
    # -----------------------------------------------------

    if address_id:
        address_id = (
            address_id.strip()
            if isinstance(
                address_id,
                str,
            )
            else address_id
        )

        if not address_id:
            address_id = None

    if address_id:

        if not _address_belongs_to_user(
            address_id,
            user,
        ):
            frappe.throw(
                _(
                    "You are not allowed to update this address."
                ),
                frappe.PermissionError,
            )

        address = frappe.get_doc(
            "Address",
            address_id,
        )

    else:

        address = frappe.get_doc(
            {
                "doctype": "Address",
            }
        )

        # -------------------------------------------------
        # LINK ADDRESS TO CURRENT USER
        # -------------------------------------------------

        address.append(
            "links",
            {
                "link_doctype": "User",
                "link_name": user,
            },
        )

    # =====================================================
    # IMPORTANT ERPNext COMPATIBILITY FIX
    # =====================================================
    #
    # Your installed ERPNext Address validator accesses
    # self.is_your_company_address.
    #
    # Your Address DocType does not have that field.
    #
    # We are NOT showing or selecting this field in UI.
    #
    # We simply provide the runtime attribute as False
    # so ERPNext validation treats this as a normal
    # customer/user address.
    #
    address.is_your_company_address = 0

    # -----------------------------------------------------
    # ADDRESS DATA
    # -----------------------------------------------------

    # address_title is used for recipient name.
    address.address_title = full_name

    address.address_type = address_type

    address.address_line1 = line1

    address.address_line2 = line2

    address.city = city

    address.state = state

    address.pincode = pincode

    address.country = country

    address.phone = phone

    address.email_id = user

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    address.is_primary_address = (
        1 if is_default else 0
    )

    address.save(
        ignore_permissions=True
    )

    # =====================================================
    # DEFAULT ADDRESS LOGIC
    # =====================================================
    #
    # Billing and Shipping have independent preferred
    # addresses.
    #
    # Example:
    #
    # Home Shipping    -> preferred
    # Office Shipping  -> not preferred
    #
    # Home Billing     -> preferred
    # Office Billing   -> not preferred
    #
    # So setting Shipping default does NOT remove
    # Billing default.
    # =====================================================

    if is_default:

        frappe.db.sql(
            """
            UPDATE `tabAddress`
            SET is_primary_address = 0
            WHERE name != %s
            AND address_type = %s
            AND name IN (
                SELECT parent
                FROM `tabDynamic Link`
                WHERE parenttype = 'Address'
                AND link_doctype = 'User'
                AND link_name = %s
            )
            """,
            (
                address.name,
                address_type,
                user,
            ),
        )

        # Make sure current address remains primary
        frappe.db.set_value(
            "Address",
            address.name,
            "is_primary_address",
            1,
        )

    # -----------------------------------------------------
    # IF FIRST ADDRESS OF THIS TYPE
    # MAKE IT DEFAULT AUTOMATICALLY
    # -----------------------------------------------------

    count = frappe.db.sql(
        """
        SELECT COUNT(*)
        FROM `tabAddress` a
        INNER JOIN `tabDynamic Link` dl
            ON dl.parent = a.name
        WHERE dl.parenttype = 'Address'
        AND dl.link_doctype = 'User'
        AND dl.link_name = %s
        AND a.address_type = %s
        """,
        (
            user,
            address_type,
        ),
    )

    address_count = (
        count[0][0]
        if count
        else 0
    )

    if address_count == 1:

        frappe.db.set_value(
            "Address",
            address.name,
            "is_primary_address",
            1,
        )

    frappe.db.commit()

    # -----------------------------------------------------
    # RETURN
    # -----------------------------------------------------

    return {
        "success": True,

        "message":
            "Address saved successfully.",

        "address": {
            "id": address.name,

            "name": address.name,

            "label": (
                "Preferred Billing Address"
                if address_type == "Billing"
                else "Preferred Shipping Address"
            ),

            "fullName": (
                address.address_title
                or ""
            ),

            "phone": (
                address.phone
                or ""
            ),

            "line1": (
                address.address_line1
                or ""
            ),

            "line2": (
                address.address_line2
                or ""
            ),

            "city": (
                address.city
                or ""
            ),

            "state": (
                address.state
                or ""
            ),

            "pincode": (
                address.pincode
                or ""
            ),

            "country": (
                address.country
                or ""
            ),

            "addressType": address_type,

            "isDefault": bool(
                address.is_primary_address
            ),
        },
    }


# =========================================================
# DELETE ADDRESS
# =========================================================

@frappe.whitelist(methods=["POST"])
def delete_address(
    address_id=None,
):
    user = _get_current_user()

    if not address_id:
        frappe.throw(
            _("Address ID is required.")
        )

    if not _address_belongs_to_user(
        address_id,
        user,
    ):
        frappe.throw(
            _(
                "You are not allowed to delete this address."
            ),
            frappe.PermissionError,
        )

    address = frappe.get_doc(
        "Address",
        address_id,
    )

    address_type = (
        address.address_type
        or "Shipping"
    )

    was_default = bool(
        address.is_primary_address
    )

    frappe.delete_doc(
        "Address",
        address_id,
        ignore_permissions=True,
    )

    # -----------------------------------------------------
    # IF DEFAULT ADDRESS WAS DELETED
    # MAKE OLDEST SAME-TYPE ADDRESS DEFAULT
    # -----------------------------------------------------

    if was_default:

        replacement = frappe.db.sql(
            """
            SELECT a.name
            FROM `tabAddress` a
            INNER JOIN `tabDynamic Link` dl
                ON dl.parent = a.name
            WHERE dl.parenttype = 'Address'
            AND dl.link_doctype = 'User'
            AND dl.link_name = %s
            AND a.address_type = %s
            ORDER BY a.creation ASC
            LIMIT 1
            """,
            (
                user,
                address_type,
            ),
            as_dict=True,
        )

        if replacement:

            frappe.db.set_value(
                "Address",
                replacement[0].name,
                "is_primary_address",
                1,
            )

    frappe.db.commit()

    return {
        "success": True,
        "message":
            "Address deleted successfully.",
    }


# =========================================================
# SET DEFAULT ADDRESS
# =========================================================

@frappe.whitelist(methods=["POST"])
def set_default_address(
    address_id=None,
):
    user = _get_current_user()

    if not address_id:
        frappe.throw(
            _("Address ID is required.")
        )

    if not _address_belongs_to_user(
        address_id,
        user,
    ):
        frappe.throw(
            _(
                "You are not allowed to update this address."
            ),
            frappe.PermissionError,
        )

    address = frappe.get_doc(
        "Address",
        address_id,
    )

    address_type = (
        address.address_type
        or "Shipping"
    )

    # -----------------------------------------------------
    # REMOVE DEFAULT FROM SAME ADDRESS TYPE ONLY
    # -----------------------------------------------------

    frappe.db.sql(
        """
        UPDATE `tabAddress`
        SET is_primary_address = 0
        WHERE name != %s
        AND address_type = %s
        AND name IN (
            SELECT parent
            FROM `tabDynamic Link`
            WHERE parenttype = 'Address'
            AND link_doctype = 'User'
            AND link_name = %s
        )
        """,
        (
            address_id,
            address_type,
            user,
        ),
    )

    # -----------------------------------------------------
    # SET CURRENT DEFAULT
    # -----------------------------------------------------

    frappe.db.set_value(
        "Address",
        address_id,
        "is_primary_address",
        1,
    )

    frappe.db.commit()

    return {
        "success": True,
        "message":
            (
                "Preferred Billing Address updated."
                if address_type == "Billing"
                else "Preferred Shipping Address updated."
            ),
    }