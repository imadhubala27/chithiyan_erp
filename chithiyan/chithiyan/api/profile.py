import frappe


def _split_name(full_name):
    full_name = (full_name or "").strip()

    if not full_name:
        return "", ""

    parts = full_name.split(" ", 1)

    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    return first_name, last_name


def _get_contact_name_from_address(address_doc):
    for link in address_doc.links:
        if link.link_doctype == "Contact":
            return link.link_name

    return None


# ==========================================================
# GET CONTACT ADDRESSES
# ==========================================================

@frappe.whitelist()
def get_contact_addresses():
    """
    Get all Address records which have a Contact link.

    Returns:
        [
            {
                "id": "...",
                "fullName": "...",
                "phone": "...",
                "email": "...",
                "addressLine1": "...",
                "addressLine2": "...",
                "city": "...",
                "state": "...",
                "pincode": "...",
                "country": "...",
                "type": "Home",
                "addressType": "personal",
                "contact": "..."
            }
        ]
    """

    addresses = frappe.get_all(
        "Address",
        fields=[
            "name",
            "address_title",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "pincode",
            "country",
            "phone",
            "email_id",
        ],
        order_by="creation desc",
    )

    result = []

    for row in addresses:

        address = frappe.get_doc("Address", row.name)

        # --------------------------------------------------
        # FIND CONTACT LINK
        # --------------------------------------------------

        contact_name = _get_contact_name_from_address(address)

        # Only return Address records linked to Contact
        if not contact_name:
            continue

        contact_data = {
            "name": "",
            "fullName": "",
            "phone": "",
            "email": "",
        }

        # --------------------------------------------------
        # CONTACT DATA
        # --------------------------------------------------

        if frappe.db.exists("Contact", contact_name):

            contact = frappe.get_doc(
                "Contact",
                contact_name,
            )

            # Phone
            phone = ""

            for phone_row in contact.phone_nos:
                if phone_row.is_primary_mobile_no:
                    phone = phone_row.phone
                    break

            if not phone and contact.phone_nos:
                phone = contact.phone_nos[0].phone

            # Email
            email = ""

            for email_row in contact.email_ids:
                if email_row.is_primary:
                    email = email_row.email_id
                    break

            if not email and contact.email_ids:
                email = contact.email_ids[0].email_id

            contact_data = {
                "name": contact.name,
                "fullName": " ".join(
                    filter(
                        None,
                        [
                            contact.first_name,
                            contact.last_name,
                        ],
                    )
                ),
                "phone": phone,
                "email": email,
            }

        # --------------------------------------------------
        # RESPONSE
        # --------------------------------------------------

        result.append(
            {
                # Actual Frappe Address ID
                "id": row.name,

                "fullName": (
                    contact_data.get("fullName")
                    or row.address_title
                    or ""
                ),

                "phone": (
                    contact_data.get("phone")
                    or row.phone
                    or ""
                ),

                "email": (
                    contact_data.get("email")
                    or row.email_id
                    or ""
                ),

                "addressLine1": row.address_line1 or "",
                "addressLine2": row.address_line2 or "",
                "city": row.city or "",
                "state": row.state or "",
                "pincode": row.pincode or "",
                "country": row.country or "India",

                # Frontend address type
                "type": "Home",
                "addressType": "personal",

                # Linked Contact
                "contact": contact_name,
            }
        )

    return result


# ==========================================================
# SAVE / UPDATE CONTACT + ADDRESS
# ==========================================================

@frappe.whitelist()
def save_contact_address(data):
    """
    Create or update Contact + Address.

    CREATE:
        id is not provided
        -> New Contact
        -> New Address

    UPDATE:
        id is provided
        -> Existing Address is loaded
        -> Existing linked Contact is loaded
        -> Same Contact updated
        -> Same Address updated
    """

    # --------------------------------------------------
    # PARSE DATA
    # --------------------------------------------------

    if isinstance(data, str):
        data = frappe.parse_json(data)

    data = data or {}

    # --------------------------------------------------
    # BASIC DATA
    # --------------------------------------------------

    full_name = (data.get("fullName") or "").strip()
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()

    address_line1 = (data.get("addressLine1") or "").strip()
    address_line2 = (data.get("addressLine2") or "").strip()

    city = (data.get("city") or "").strip()
    state = (data.get("state") or "").strip()
    pincode = (data.get("pincode") or "").strip()
    country = (data.get("country") or "India").strip()

    address_id = (data.get("id") or "").strip()

    address_type = (
        data.get("addressType")
        or "personal"
    )

    frontend_type = (
        data.get("type")
        or "Home"
    )

    # --------------------------------------------------
    # VALIDATION
    # --------------------------------------------------

    if not full_name:
        frappe.throw("Full Name is required")

    if not address_line1:
        frappe.throw("Address Line 1 is required")

    if not city:
        frappe.throw("City is required")

    if not state:
        frappe.throw("State is required")

    if not pincode:
        frappe.throw("Pincode is required")

    # --------------------------------------------------
    # DETERMINE CREATE / UPDATE
    # --------------------------------------------------

    is_update = False
    address = None
    contact = None

    # ==================================================
    # UPDATE CASE
    # ==================================================

    if address_id:

        # IMPORTANT:
        # If ID is provided but Address does not exist,
        # NEVER create a new Address.
        if not frappe.db.exists(
            "Address",
            address_id,
        ):
            frappe.throw(
                f"Address '{address_id}' not found. "
                "Please refresh the Address Book and try again."
            )

        is_update = True

        # Existing Address
        address = frappe.get_doc(
            "Address",
            address_id,
        )

        # Find linked Contact
        contact_name = _get_contact_name_from_address(
            address
        )

        # Existing Contact
        if (
            contact_name
            and frappe.db.exists(
                "Contact",
                contact_name,
            )
        ):
            contact = frappe.get_doc(
                "Contact",
                contact_name,
            )

        # If Address has no Contact link,
        # create Contact and link it below.
        if not contact:
            contact = frappe.new_doc(
                "Contact"
            )

    # ==================================================
    # CREATE CASE
    # ==================================================

    else:

        contact = frappe.new_doc(
            "Contact"
        )

        address = frappe.new_doc(
            "Address"
        )

    # ==================================================
    # CONTACT DATA
    # ==================================================

    first_name, last_name = _split_name(
        full_name
    )

    contact.first_name = first_name
    contact.last_name = last_name

    # --------------------------------------------------
    # PHONE
    # --------------------------------------------------

    contact.set(
        "phone_nos",
        [],
    )

    if phone:
        contact.append(
            "phone_nos",
            {
                "phone": phone,
                "is_primary_mobile_no": 1,
            },
        )

    # --------------------------------------------------
    # EMAIL
    # --------------------------------------------------

    contact.set(
        "email_ids",
        [],
    )

    if email:
        contact.append(
            "email_ids",
            {
                "email_id": email,
                "is_primary": 1,
            },
        )

    # --------------------------------------------------
    # SAVE CONTACT
    # --------------------------------------------------

    contact.save(
        ignore_permissions=True
    )

    # ==================================================
    # ADDRESS DATA
    # ==================================================

    address.address_title = full_name

    address.address_line1 = address_line1
    address.address_line2 = address_line2

    address.city = city
    address.state = state
    address.pincode = pincode
    address.country = country

    address.phone = phone
    address.email_id = email

    # ERPNext Address Type
    address.address_type = "Shipping"

    # --------------------------------------------------
    # CONTACT LINK
    # --------------------------------------------------

    address.set(
        "links",
        []
    )

    address.append(
        "links",
        {
            "link_doctype": "Contact",
            "link_name": contact.name,
        },
    )

    # --------------------------------------------------
    # SAVE ADDRESS
    # --------------------------------------------------

    address.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    # ==================================================
    # RESPONSE
    # ==================================================

    return {
        "success": True,

        "action": (
            "updated"
            if is_update
            else "created"
        ),

        "contact": {
            "name": contact.name,
            "fullName": full_name,
            "phone": phone,
            "email": email,
        },

        "address": {
            # VERY IMPORTANT:
            # This is actual Frappe Address name
            "id": address.name,

            "fullName": full_name,
            "phone": phone,
            "email": email,

            "addressLine1": (
                address.address_line1
                or ""
            ),

            "addressLine2": (
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
                or "India"
            ),

            "type": frontend_type,

            "addressType": address_type,

            "contact": contact.name,
        },
    }


# ==========================================================
# DELETE CONTACT + ADDRESS
# ==========================================================

@frappe.whitelist()
def delete_contact_address(address_id):
    """
    Delete Address and its linked Contact.
    """

    if not address_id:
        frappe.throw(
            "Address ID is required"
        )

    # --------------------------------------------------
    # CHECK ADDRESS
    # --------------------------------------------------

    if not frappe.db.exists(
        "Address",
        address_id,
    ):
        frappe.throw(
            "Address not found"
        )

    # --------------------------------------------------
    # GET ADDRESS
    # --------------------------------------------------

    address = frappe.get_doc(
        "Address",
        address_id,
    )

    # --------------------------------------------------
    # FIND CONTACT
    # --------------------------------------------------

    contact_name = (
        _get_contact_name_from_address(
            address
        )
    )

    # --------------------------------------------------
    # DELETE ADDRESS
    # --------------------------------------------------

    frappe.delete_doc(
        "Address",
        address_id,
        ignore_permissions=True,
    )

    # --------------------------------------------------
    # DELETE CONTACT
    # --------------------------------------------------

    if (
        contact_name
        and frappe.db.exists(
            "Contact",
            contact_name,
        )
    ):
        frappe.delete_doc(
            "Contact",
            contact_name,
            ignore_permissions=True,
        )

    frappe.db.commit()

    return {
        "success": True,
        "message": (
            "Contact and Address "
            "deleted successfully"
        ),
    }