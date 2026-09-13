# Copyright (c) 2026, techpanjab.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Testimonial(Document):
    pass


@frappe.whitelist(allow_guest=True)
def get_testimonials():
    testimonials = frappe.get_all(
        "Testimonial",
        fields=[
            "name",
            "customer_name",
            "rating",
            "description",
            "photo",
        ],
        order_by="modified desc",
    )

    return testimonials