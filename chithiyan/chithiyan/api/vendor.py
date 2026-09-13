import frappe
from frappe import _

@frappe.whitelist(methods=["POST"])
def create_vendor_lead(
    company_name=None,
    contact_person=None,
    email=None,
    mobile=None,
    description=None,
):
    # ---------------------------------------------------------
    # CLEAN DATA
    # ---------------------------------------------------------

    company_name = (company_name or "").strip()
    contact_person = (contact_person or "").strip()
    email = (email or "").strip()
    mobile = (mobile or "").strip()
    description = (description or "").strip()

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    if not company_name:
        frappe.throw(
            _("Company / Brand Name is required.")
        )

    if not contact_person:
        frappe.throw(
            _("Contact Person Name is required.")
        )

    if not email:
        frappe.throw(
            _("Email Address is required.")
        )

    if not mobile:
        frappe.throw(
            _("Mobile Phone is required.")
        )

    if not description:
        frappe.throw(
            _("Product / Service description is required.")
        )

    # ---------------------------------------------------------
    # CHECK EXISTING LEAD
    # ---------------------------------------------------------

    existing_lead = frappe.db.get_value(
        "Lead",
        {
            "email_id": email,
        },
        "name",
    )

    if existing_lead:
        return {
            "success": True,
            "existing": True,
            "message": (
                "Your partnership request has already been received."
            ),
            "lead": existing_lead,
        }

    # ---------------------------------------------------------
    # CREATE LEAD
    # ---------------------------------------------------------

    lead = frappe.get_doc(
        {
            "doctype": "Lead",

            "lead_name": contact_person,

            "company_name": company_name,

            "email_id": email,

            "mobile_no": mobile,

        }
    )

    # ---------------------------------------------------------
    # ADD DESCRIPTION TO LEAD NOTES
    # ---------------------------------------------------------

    if description:
        lead.append(
            "notes",
            {
                "note": description,
            },
        )

    # ---------------------------------------------------------
    # INSERT
    # ---------------------------------------------------------

    lead.insert(
        ignore_permissions=True
    )

    frappe.db.commit()

    # ---------------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------------

    return {
        "success": True,

        "existing": False,

        "message": (
            "Partnership request submitted successfully."
        ),

        "lead": lead.name,
    }