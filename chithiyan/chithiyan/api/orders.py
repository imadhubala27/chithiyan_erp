import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_days, cint, flt, nowdate

SUBMIT_ORDER = False
DELIVERY_DAYS = 3
MAX_QTY_PER_ITEM = 100


def get_item_code(cart_item_id: str) -> str:
	"""Map a cart item id to an ERPNext Item Code. Change here if they differ."""
	return cart_item_id


def _get_default(fieldname, doctype, fallback):
	return frappe.db.get_single_value(doctype, fieldname) or fallback


def _find_customer_by_email(email: str):
	contacts = frappe.get_all(
		"Contact Email",
		filters={"email_id": email, "parenttype": "Contact"},
		pluck="parent",
	)
	for contact in contacts:
		customer = frappe.db.get_value(
			"Dynamic Link",
			{"parent": contact, "parenttype": "Contact", "link_doctype": "Customer"},
			"link_name",
		)
		if customer:
			return customer
	return None


def _get_or_create_customer(name: str, email: str, phone: str) -> str:
	existing = _find_customer_by_email(email)
	if existing:
		return existing

	customer = frappe.get_doc({
		"doctype": "Customer",
		"customer_name": name,
		"customer_type": "Individual",
		"customer_group": _get_default("customer_group", "Selling Settings", "Individual"),
		"territory": _get_default("territory", "Selling Settings", "All Territories"),
	}).insert(ignore_permissions=True)

	contact = frappe.get_doc({
		"doctype": "Contact",
		"first_name": name,
		"email_ids": [{"email_id": email, "is_primary": 1}],
		"phone_nos": [{"phone": phone, "is_primary_mobile_no": 1}] if phone else [],
		"links": [{"link_doctype": "Customer", "link_name": customer.name}],
	}).insert(ignore_permissions=True)

	customer.db_set("customer_primary_contact", contact.name)
	return customer.name


def _create_shipping_address(customer: str, shipping: dict) -> str:
	address = frappe.get_doc({
		"doctype": "Address",
		"address_title": shipping["fullName"],
		"address_type": "Shipping",
		"address_line1": shipping["line1"],
		"city": shipping["city"],
		"state": shipping["state"],
		"pincode": shipping["pincode"],
		"country": shipping.get("country") or "India",
		"phone": shipping.get("phone"),
		"links": [{"link_doctype": "Customer", "link_name": customer}],
	}).insert(ignore_permissions=True)
	return address.name


def _build_items(cart_items: list) -> list:
	if not cart_items:
		frappe.throw(_("Cart is empty"))

	rows = []
	for item in cart_items:
		code = get_item_code(str(item.get("id", "")))
		if not frappe.db.exists("Item", code):
			frappe.throw(_("Item not found: {0}").format(code))

		qty = cint(item.get("qty"))
		if qty < 1 or qty > MAX_QTY_PER_ITEM:
			frappe.throw(_("Invalid quantity for {0}").format(code))

		# Price comes from the server so it cannot be changed from the browser.
		server_rate = flt(frappe.db.get_value("Item", code, "standard_rate"))
		rate = server_rate if server_rate > 0 else flt(item.get("price"))

		rows.append({
			"item_code": code,
			"qty": qty,
			"rate": rate,
			"delivery_date": add_days(nowdate(), DELIVERY_DAYS),
		})
	return rows


def _make_so_from_quotation(quotation_name: str):
	"""
	Guest user ke paas Sales Order 'create' permission nahi hoti, isliye
	mapping ke dauran temporarily Administrator banate hain.
	"""
	from erpnext.selling.doctype.quotation.quotation import make_sales_order

	prev_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		return make_sales_order(quotation_name)
	finally:
		frappe.set_user(prev_user)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def create_sales_order(payload=None):
	"""Submit the customer's Cart quotation and create a linked Sales Order."""
	from chithiyan.chithiyan.api.quotations import sync_quotation

	data = frappe.parse_json(payload) if payload else {}

	customer_data = data.get("customer") or {}
	shipping = data.get("shipping") or {}

	email = (customer_data.get("email") or "").strip().lower()
	if not email:
		frappe.throw(_("Customer email is required"))

	for key in ("fullName", "phone", "line1", "city", "state", "pincode"):
		if not (shipping.get(key) or "").strip():
			frappe.throw(_("Shipping field missing: {0}").format(key))

	try:
		customer = _get_or_create_customer(
			customer_data.get("name") or shipping["fullName"],
			email,
			customer_data.get("phone") or shipping["phone"],
		)
		address = _create_shipping_address(customer, shipping)

		# 1. Make the Cart quotation match what is being checked out, then submit it.
		quotation, skipped = sync_quotation(customer, "Cart", data.get("items") or [])
		if not quotation:
			frappe.throw(_("Cart is empty"))
		if skipped:
			frappe.throw(_("Item not found: {0}").format(", ".join(map(str, skipped))))
		quotation.flags.ignore_permissions = True
		quotation.submit()

		# 2. Sales Order from the quotation (keeps the quotation link on every row).
		so = _make_so_from_quotation(quotation.name)
		delivery_date = add_days(nowdate(), DELIVERY_DAYS)
		so.transaction_date = nowdate()
		so.delivery_date = delivery_date
		for row in so.items:
			row.delivery_date = delivery_date

		so.shipping_address_name = address
		so.customer_address = address
		so.contact_email = email
		so.contact_mobile = shipping["phone"]

		notes = []
		if data.get("occasion"):
			notes.append(f"Occasion: {data['occasion']}")
		if data.get("specialNote"):
			notes.append(f"Delivery note: {data['specialNote']}")
		if data.get("giftPreference"):
			notes.append(f"Gift preference: {data['giftPreference']}")
		so.terms = "<br>".join(notes)

		delivery_fee = flt(data.get("deliveryFee"))
		delivery_account = frappe.conf.get("chithiyan_delivery_account")
		if delivery_fee > 0 and delivery_account:
			so.append("taxes", {
				"charge_type": "Actual",
				"account_head": delivery_account,
				"description": "Delivery Charge",
				"tax_amount": delivery_fee,
			})

		wallet_paid = flt(data.get("walletPaid"))
		if wallet_paid > 0:
			so.apply_discount_on = "Grand Total"
			so.discount_amount = wallet_paid

		so.flags.ignore_permissions = True
		so.insert(ignore_permissions=True)
		if SUBMIT_ORDER:
			so.submit()

		frappe.db.commit()

		return {
			"name": so.name,
			"quotation": quotation.name,
			"grand_total": so.grand_total,
			"status": so.status,
		}

	except frappe.ValidationError:
		raise
	except Exception as e:
		frappe.log_error(title="Website Sales Order failed", message=frappe.get_traceback())
		if frappe.conf.get("developer_mode"):
			frappe.throw(str(e))
		frappe.throw(_("Could not place your order. Please try again."))