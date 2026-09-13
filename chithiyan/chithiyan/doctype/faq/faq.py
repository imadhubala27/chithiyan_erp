# Copyright (c) 2026, techpanjab.com and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class FAQ(Document):
	pass


import frappe


@frappe.whitelist(allow_guest=True)
def get_faqs():
    faqs = frappe.get_all(
        "FAQ",
        fields=[
            "name",
            "question",
            "answer",
        ],
        order_by="modified desc",
    )

    return faqs