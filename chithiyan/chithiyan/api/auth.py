import frappe


@frappe.whitelist(allow_guest=True)
def signup(full_name, email, password):
    """Create a Website User from the Chithiyan frontend."""

    if not full_name or not email or not password:
        frappe.throw("Full name, email and password are required.")

    email = email.strip().lower()
    full_name = full_name.strip()

    # Check if user already exists
    if frappe.db.exists("User", email):
        frappe.throw("An account with this email already exists.")

    # Create user
    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": full_name,
            "new_password": password,
            "enabled": 1,
            "send_welcome_email": 0,
            "user_type": "Website User",
        }
    )

    user.insert(ignore_permissions=True)

    frappe.db.commit()

    return {
        "success": True,
        "message": "User created successfully.",
        "email": email,
    }