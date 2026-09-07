import random
import re

import frappe
from frappe import _


frappe.flags.ignore_csrf = True

@frappe.whitelist(
    allow_guest=True,
    methods=["POST"]
)
def signup():
    email = _get_email()
    full_name = _get_full_name()

    password = (
        frappe.form_dict.get("password")
        or ""
    )

    _validate_email(email)

    if not full_name:
        frappe.throw(
            _("Please enter your full name.")
        )

    _validate_password(password)

    if frappe.db.exists(
        "User",
        {"name": email}
    ):
        frappe.throw(
            _("An account with this email already exists.")
        )

    name_parts = full_name.split()

    first_name = name_parts[0]
    last_name = ""

    if len(name_parts) > 1:
        last_name = " ".join(
            name_parts[1:]
        )

    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "enabled": 1,
            "user_type": "Website User",
            "send_welcome_email": 0,
            "new_password": password,
        }
    )

    user.insert(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "success": True,
        "email": email,
        "message": "Account created successfully.",
    }


def _get_email(value=None):
    email = (
        value
        or frappe.form_dict.get("email")
        or ""
    ).strip().lower()

    return email


def _get_full_name(value=None):
    return (
        value
        or frappe.form_dict.get("full_name")
        or ""
    ).strip()


def _validate_email(email):
    if not email:
        frappe.throw(_("Email address is required."))

    pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"

    if not re.match(pattern, email):
        frappe.throw(
            _("Please enter a valid email address.")
        )


def _validate_password(password):
    if not password:
        frappe.throw(
            _("Password is required.")
        )

    if len(password) < 6:
        frappe.throw(
            _("Password must be at least 6 characters.")
        )


@frappe.whitelist(
    allow_guest=True,
    methods=["POST"]
)
def forgot_password():
    email = _get_email()

    _validate_email(email)

    generic_message = (
        "If an account exists with this email, "
        "a verification code has been sent."
    )

    user_name = frappe.db.get_value(
        "User",
        {
            "name": email,
            "enabled": 1,
        },
        "name",
    )

    if not user_name:
        return {
            "success": True,
            "message": generic_message,
        }

    # ==========================================
    # EXACTLY 6 DIGIT NUMERIC OTP
    # ==========================================

    otp = str(
        random.randint(100000, 999999)
    )

    # ==========================================
    # STORE OTP FOR 10 MINUTES
    # ==========================================

    cache_key = (
        f"chithiyan_password_reset:{email}"
    )

    frappe.cache().set_value(
        cache_key,
        otp,
        expires_in_sec=600,
    )

    # ==========================================
    # USER
    # ==========================================

    user_doc = frappe.get_doc(
        "User",
        user_name
    )

    recipient_name = (
        user_doc.full_name
        or user_doc.first_name
        or email
    )

    # ==========================================
    # EMAIL
    # ==========================================

    subject = "Chithiyan Password Reset Code"

    message = f"""
    <div style="font-family: Arial, sans-serif;">

        <h2>Chithiyan Password Reset</h2>

        <p>
            Hello {frappe.utils.escape_html(recipient_name)},
        </p>

        <p>
            We received a request to reset your
            Chithiyan account password.
        </p>

        <p>
            Your verification code is:
        </p>

        <div style="
            font-size: 28px;
            font-weight: bold;
            letter-spacing: 8px;
            padding: 15px;
            background: #f7f1f1;
            width: fit-content;
            border-radius: 8px;
        ">
            {otp}
        </div>

        <p>
            This code will expire in 10 minutes.
        </p>

        <p>
            If you did not request this password reset,
            please ignore this email.
        </p>

        <p>
            Regards,<br>
            Chithiyan Team
        </p>

    </div>
    """

    frappe.sendmail(
        recipients=[email],
        subject=subject,
        message=message,
    )

    return {
        "success": True,
        "message": generic_message,
    }

@frappe.whitelist(
    allow_guest=True,
    methods=["POST"]
)
def reset_password():
    email = _get_email()

    otp = (
        frappe.form_dict.get("otp")
        or ""
    ).strip()

    new_password = (
        frappe.form_dict.get("new_password")
        or ""
    )

    _validate_email(email)

    # ==========================================
    # OTP VALIDATION
    # ==========================================

    if not re.match(
        r"^\d{6}$",
        otp
    ):
        frappe.throw(
            _(
                "Please enter a valid "
                "6-digit verification code."
            )
        )

    # ==========================================
    # PASSWORD
    # ==========================================

    _validate_password(
        new_password
    )

    # ==========================================
    # GET OTP
    # ==========================================

    cache_key = (
        f"chithiyan_password_reset:{email}"
    )

    stored_otp = frappe.cache().get_value(
        cache_key
    )

    if not stored_otp:
        frappe.throw(
            _(
                "Verification code has expired. "
                "Please request a new code."
            )
        )

    if str(stored_otp) != otp:
        frappe.throw(
            _("Incorrect verification code.")
        )

    # ==========================================
    # FIND USER
    # ==========================================

    user_name = frappe.db.get_value(
        "User",
        {
            "name": email,
            "enabled": 1,
        },
        "name",
    )

    if not user_name:
        frappe.throw(
            _("Unable to reset password.")
        )

    # ==========================================
    # UPDATE PASSWORD
    # ==========================================

    user = frappe.get_doc(
        "User",
        user_name
    )

    user.new_password = new_password

    user.save(
        ignore_permissions=True
    )

    # ==========================================
    # DELETE OTP
    # ==========================================

    frappe.cache().delete_value(
        cache_key
    )

    frappe.db.commit()

    return {
        "success": True,
        "message": "Password updated successfully.",
    }