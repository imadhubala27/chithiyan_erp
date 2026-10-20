# Copyright (c) 2026, techpanjab.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WebsiteReel(Document):
	pass


@frappe.whitelist(allow_guest=True)
def get_published_reels():

	records = frappe.get_all(
		"Website Reel",
		filters={
			"is_published": 1,
			"is_active": 1,
			"video_file": ["is", "set"],
		},
		fields=[
			"name",
			"reel_title",
			"video_file",
			"thumbnail",
			"description",
		],
		order_by="modified desc",
	)

	return [
		{
			"id": record.name,
			"title": record.reel_title or "",
			"category": "Handcrafted Gifts",
			"videoUrl": record.video_file,
			"thumbnail": record.thumbnail or "",
			"description": record.description or "",
		}
		for record in records
	]