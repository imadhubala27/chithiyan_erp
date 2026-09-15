import frappe
from frappe.model.document import Document
from frappe.utils import random_string


class VendorRegistration(Document):
    pass


@frappe.whitelist(allow_guest=True)
def create_vendor_registration(
    first_name=None,
    last_name=None,
    email=None,
    mobile_phone=None,
    address=None,
    city=None,
    country=None,
    shipping_method=None,
    company=None,
    designation=None,
    website=None,
    products_dealing_in=None,
):
    # ---------------------------------
    # Required field validation
    # ---------------------------------

    required_fields = {
        "First Name": first_name,
        "Last Name": last_name,
        "Email": email,
        "Mobile Phone": mobile_phone,
        "Address": address,
        "City": city,
        "Country": country,
        "Products Dealing-In": products_dealing_in,
    }

    for field_label, value in required_fields.items():
        if not value or not str(value).strip():
            frappe.throw(f"{field_label} is required")

    # ---------------------------------
    # Create Vendor Registration
    # ---------------------------------

    vendor_registration = frappe.get_doc(
        {
            "doctype": "Vendor Registration",
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "email": email.strip(),
            "mobile_phone": mobile_phone.strip(),
            "address": address.strip(),
            "city": city.strip(),
            "country": country.strip(),
            "shipping_method": shipping_method,
            "company": company,
            "designation": designation,
            "website": website,
            "products_dealing_in": products_dealing_in.strip(),
            "status": "Pending",
        }
    )

    vendor_registration.insert(ignore_permissions=True)

    frappe.db.commit()

    return {
        "success": True,
        "message": "Vendor registration submitted successfully.",
        "name": vendor_registration.name,
    }


@frappe.whitelist()
def create_supplier(vendor_registration):
    """
    Create Supplier, Contact, Address and User
    from Vendor Registration.
    """

    # ---------------------------------
    # Get Vendor Registration
    # ---------------------------------

    vendor = frappe.get_doc(
        "Vendor Registration",
        vendor_registration
    )

    # ---------------------------------
    # Already Created
    # ---------------------------------

    if vendor.supplier:
        return {
            "success": True,
            "message": "Supplier is already created.",
            "supplier": vendor.supplier,
            "contact": vendor.contact,
            "address": vendor.address_link,
            "user": vendor.user,
            "status": vendor.status,
        }

    # ---------------------------------
    # Validate Status
    # ---------------------------------

    if vendor.status == "Rejected":
        frappe.throw(
            "Supplier cannot be created for a rejected vendor registration."
        )

    # ---------------------------------
    # Full Name
    # ---------------------------------

    full_name = f"{vendor.first_name} {vendor.last_name}".strip()

    supplier_name = vendor.company or full_name

    if not supplier_name:
        frappe.throw(
            "Supplier name could not be determined."
        )

    # ---------------------------------
    # Supplier Group
    # ---------------------------------

    supplier_group = frappe.db.get_single_value(
        "Buying Settings",
        "supplier_group"
    )

    if not supplier_group:
        supplier_group = frappe.db.get_value(
            "Supplier Group",
            {},
            "name",
            order_by="lft asc"
        )

    if not supplier_group:
        frappe.throw(
            "No Supplier Group found. "
            "Please create a Supplier Group first."
        )

    # ---------------------------------
    # CREATE SUPPLIER
    # ---------------------------------

    supplier = frappe.get_doc(
        {
            "doctype": "Supplier",
            "supplier_name": supplier_name,
            "supplier_group": supplier_group,
            "supplier_type": "Company",
        }
    )

    supplier.insert(ignore_permissions=True)

    # ---------------------------------
    # CREATE CONTACT
    # ---------------------------------

    contact = frappe.get_doc(
        {
            "doctype": "Contact",
            "first_name": vendor.first_name,
            "last_name": vendor.last_name,
            "company_name": supplier.name,
            "is_primary_contact": 1,
        }
    )

    # Email
    contact.append(
        "email_ids",
        {
            "email_id": vendor.email,
            "is_primary": 1,
        }
    )

    # Mobile
    contact.append(
        "phone_nos",
        {
            "phone": vendor.mobile_phone,
            "is_primary_mobile_no": 1,
        }
    )

    # Link Contact with Supplier
    contact.append(
        "links",
        {
            "link_doctype": "Supplier",
            "link_name": supplier.name,
        }
    )

    contact.insert(ignore_permissions=True)

    # ---------------------------------
    # CREATE ADDRESS
    # ---------------------------------

    address = frappe.get_doc(
        {
            "doctype": "Address",
            "address_title": supplier.name,
            "address_type": "Billing",
            "address_line1": vendor.address,
            "city": vendor.city,
            "country": vendor.country,
            "email_id": vendor.email,
            "phone": vendor.mobile_phone,
        }
    )

    # Link Address with Supplier
    address.append(
        "links",
        {
            "link_doctype": "Supplier",
            "link_name": supplier.name,
        }
    )

    address.insert(ignore_permissions=True)


	user_name = vendor.email.strip().lower()

	existing_user = frappe.db.exists(
		"User",
		user_name
	)

	if existing_user:
		# ---------------------------------
		# Existing User
		# ---------------------------------

		user = frappe.get_doc(
			"User",
			user_name
		)

	else:
		# ---------------------------------
		# New User
		# ---------------------------------

		generated_password = random_string(12)

		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": user_name,
				"first_name": vendor.first_name,
				"last_name": vendor.last_name,
				"mobile_no": vendor.mobile_phone,
				"user_type": "Website User",
				"enabled": 1,
				"send_welcome_email": 1,
				"new_password": generated_password,
			}
		)

		user.insert(ignore_permissions=True)


	# ---------------------------------
	# ADD ONLY SUPPLIER ROLE
	# ---------------------------------

	has_supplier_role = any(
		role.role == "Supplier"
		for role in user.roles
	)

	if not has_supplier_role:
		user.append(
			"roles",
			{
				"role": "Supplier"
			}
		)

		user.save(ignore_permissions=True)
    frappe.db.commit()

    # ---------------------------------
    # RESPONSE
    # ---------------------------------

    return {
        "success": True,
        "message": (
            "Supplier, Contact, Address and User "
            "created successfully."
        ),
        "supplier": supplier.name,
        "contact": contact.name,
        "address": address.name,
        "user": user.name,
        "vendor_registration": vendor.name,
        "status": vendor.status,
    }