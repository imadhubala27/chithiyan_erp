import frappe

from frappe import _
from frappe.model.document import Document
from frappe.utils.file_manager import save_file


class PersonalizedGiftRequest(Document):
    pass


@frappe.whitelist(allow_guest=True)
def create_personalized_gift_request(
    full_name=None,
    email_address=None,
    mobile_number=None,
    whatsapp_number=None,
    city=None,
    state=None,
    pincode=None,
    occasion=None,
    budget=None,
    delivery_date=None,
    preferred_contact_method=None,
    gift_type=None,
    detailed_custom_request=None,
):
    # -----------------------------------------
    # REQUIRED FIELDS
    # -----------------------------------------

    required_fields = {
        "Full Name": full_name,
        "Email Address": email_address,
        "Mobile Number": mobile_number,
        "City": city,
        "State": state,
        "Pincode": pincode,
        "Detailed Custom Request": detailed_custom_request,
    }

    for field_label, value in required_fields.items():
        if not value or not str(value).strip():
            frappe.throw(
                _("{0} is required.").format(field_label)
            )

    # -----------------------------------------
    # CREATE PERSONALIZED GIFT REQUEST
    # -----------------------------------------

    gift_request = frappe.get_doc(
        {
            "doctype": "Personalized Gift Request",

            "full_name": full_name.strip(),

            "email_address": email_address.strip(),

            "mobile_number": mobile_number.strip(),

            "whatsapp_number": (
                whatsapp_number.strip()
                if whatsapp_number
                else None
            ),

            "city": city.strip(),

            "state": state.strip(),

            "pincode": pincode.strip(),

            "occasion": (
                occasion.strip()
                if occasion
                else None
            ),

            "budget": budget or None,

            "delivery_date": delivery_date or None,

            "preferred_contact_method": (
                preferred_contact_method
                if preferred_contact_method
                else "WhatsApp"
            ),

            "gift_type": (
                gift_type.strip()
                if gift_type
                else None
            ),

            "detailed_custom_request": (
                detailed_custom_request.strip()
            ),
        }
    )

    # -----------------------------------------
    # INSERT AS DRAFT
    # -----------------------------------------

    gift_request.insert(
        ignore_permissions=True
    )

    # -----------------------------------------
    # GET UPLOADED IMAGES
    # -----------------------------------------

    uploaded_files = []

    if frappe.request and frappe.request.files:
        uploaded_files = (
            frappe.request.files.getlist("files")
        )

    # -----------------------------------------
    # SAVE IMAGES AS ATTACHMENTS
    # -----------------------------------------

    attachment_count = 0

    for uploaded_file in uploaded_files:

        if not uploaded_file:
            continue

        if not uploaded_file.filename:
            continue

        file_name = uploaded_file.filename

        # Read file content
        file_content = uploaded_file.read()

        if not file_content:
            continue

        # Maximum 5 MB per image
        max_file_size = 5 * 1024 * 1024

        if len(file_content) > max_file_size:
            frappe.throw(
                _(
                    "Image '{0}' is larger than 5 MB."
                ).format(file_name)
            )

        # Validate image extension
        allowed_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        }

        extension = ""

        if "." in file_name:
            extension = (
                "."
                + file_name.rsplit(".", 1)[1].lower()
            )

        if extension not in allowed_extensions:
            frappe.throw(
                _(
                    "Invalid image format for '{0}'. "
                    "Only JPG, JPEG, PNG and WEBP images "
                    "are allowed."
                ).format(file_name)
            )

        # Save as private attachment
        save_file(
            fname=file_name,
            content=file_content,
            dt="Personalized Gift Request",
            dn=gift_request.name,
            folder="Home/Attachments",
            is_private=1,
        )

        attachment_count += 1

    # -----------------------------------------
    # COMMIT
    # -----------------------------------------

    frappe.db.commit()

    # -----------------------------------------
    # RESPONSE
    # -----------------------------------------

    return {
        "success": True,
        "message": (
            "Personalized gift request "
            "submitted successfully."
        ),
        "name": gift_request.name,
        "docstatus": gift_request.docstatus,
        "attachment_count": attachment_count,
    }