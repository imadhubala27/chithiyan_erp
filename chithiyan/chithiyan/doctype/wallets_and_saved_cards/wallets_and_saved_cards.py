# Copyright (c) 2026, techpanjab.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WalletsandSavedCards(Document):
	pass



def _get_wallet_name():
    """
    One Wallets and Saved Cards document per logged-in user.
    """
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.throw("Please login first.")

    return frappe.session.user


def _get_or_create_wallet():
    wallet_name = _get_wallet_name()

    if frappe.db.exists(
        "Wallets and Saved Cards",
        wallet_name,
    ):
        return frappe.get_doc(
            "Wallets and Saved Cards",
            wallet_name,
        )

    wallet = frappe.new_doc(
        "Wallets and Saved Cards"
    )

    wallet.name = wallet_name
    wallet.wallet_balance = 0
    wallet.wallet_active = 0

    wallet.insert(
        ignore_permissions=True
    )

    return wallet


# ==========================================================
# GET WALLET
# ==========================================================

@frappe.whitelist()
def get_wallet():

    wallet = _get_or_create_wallet()

    cards = []

    for card in wallet.saved_cards or []:
        cards.append({
            "id": card.name,
            "cardNumber": card.card_number or "",
            "cardName": card.card_name or "",
            "expiry": card.expiry or "",
            "holder": card.holder or "",
        })

    upis = []

    if wallet.saved_upis:
        upis = [
            item.strip()
            for item in wallet.saved_upis.split(",")
            if item.strip()
        ]

    paypals = []

    if wallet.saved_paypals:
        paypals = [
            item.strip()
            for item in wallet.saved_paypals.split(",")
            if item.strip()
        ]

    return {
        "id": wallet.name,
        "walletBalance": wallet.wallet_balance or 0,
        "walletActive": bool(wallet.wallet_active),
        "savedCards": cards,
        "savedUpis": upis,
        "savedPaypals": paypals,
    }


# ==========================================================
# UPDATE WALLET BALANCE
# ==========================================================

@frappe.whitelist()
def update_wallet_balance(amount):

    wallet = _get_or_create_wallet()

    amount = frappe.utils.flt(amount)

    if amount <= 0:
        frappe.throw(
            "Amount must be greater than zero."
        )

    wallet.wallet_balance = (
        frappe.utils.flt(wallet.wallet_balance)
        + amount
    )

    wallet.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "walletBalance": wallet.wallet_balance
    }


# ==========================================================
# ACTIVATE WALLET
# ==========================================================

@frappe.whitelist()
def activate_wallet():

    wallet = _get_or_create_wallet()

    wallet.wallet_active = 1

    wallet.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "walletActive": True
    }


# ==========================================================
# ADD CARD
# ==========================================================

@frappe.whitelist()
def add_card(
    card_number,
    card_name,
    expiry,
    holder,
):

    wallet = _get_or_create_wallet()

    card_number = (card_number or "").strip()
    card_name = (card_name or "").strip()
    expiry = (expiry or "").strip()
    holder = (holder or "").strip()

    if not card_number:
        frappe.throw(
            "Card number is required."
        )

    if not expiry:
        frappe.throw(
            "Card expiry is required."
        )

    if not holder:
        frappe.throw(
            "Card holder is required."
        )

    card = wallet.append(
        "saved_cards",
        {
            "card_number": card_number,
            "card_name": card_name,
            "expiry": expiry,
            "holder": holder,
        },
    )

    wallet.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "id": card.name,
        "cardNumber": card.card_number,
        "cardName": card.card_name,
        "expiry": card.expiry,
        "holder": card.holder,
    }


# ==========================================================
# UPDATE CARD
# ==========================================================

@frappe.whitelist()
def update_card(
    card_id,
    card_number,
    card_name,
    expiry,
    holder,
):

    wallet = _get_or_create_wallet()

    card = None

    for row in wallet.saved_cards or []:
        if row.name == card_id:
            card = row
            break

    if not card:
        frappe.throw(
            "Saved card not found."
        )

    card.card_number = (
        card_number or ""
    ).strip()

    card.card_name = (
        card_name or ""
    ).strip()

    card.expiry = (
        expiry or ""
    ).strip()

    card.holder = (
        holder or ""
    ).strip()

    wallet.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "id": card.name,
        "cardNumber": card.card_number,
        "cardName": card.card_name,
        "expiry": card.expiry,
        "holder": card.holder,
    }


# ==========================================================
# DELETE CARD
# ==========================================================

@frappe.whitelist()
def delete_card(card_id):

    wallet = _get_or_create_wallet()

    card = None

    for row in wallet.saved_cards or []:
        if row.name == card_id:
            card = row
            break

    if not card:
        frappe.throw(
            "Saved card not found."
        )

    wallet.remove(card)

    wallet.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "success": True,
        "cardId": card_id,
    }


# ==========================================================
# SAVE UPI
# ==========================================================

@frappe.whitelist()
def save_upi(upi):

    wallet = _get_or_create_wallet()

    upi = (upi or "").strip()

    if not upi:
        frappe.throw(
            "UPI ID is required."
        )

    existing = []

    if wallet.saved_upis:
        existing = [
            item.strip()
            for item in wallet.saved_upis.split(",")
            if item.strip()
        ]

    if upi not in existing:
        existing.append(upi)

    wallet.saved_upis = ", ".join(existing)

    wallet.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "savedUpis": existing
    }


# ==========================================================
# DELETE UPI
# ==========================================================

@frappe.whitelist()
def delete_upi(upi):

    wallet = _get_or_create_wallet()

    upi = (upi or "").strip()

    existing = []

    if wallet.saved_upis:
        existing = [
            item.strip()
            for item in wallet.saved_upis.split(",")
            if item.strip()
        ]

    existing = [
        item
        for item in existing
        if item != upi
    ]

    wallet.saved_upis = ", ".join(existing)

    wallet.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "savedUpis": existing
    }


# ==========================================================
# SAVE PAYPAL
# ==========================================================

@frappe.whitelist()
def save_paypal(email):

    wallet = _get_or_create_wallet()

    email = (email or "").strip()

    if not email:
        frappe.throw(
            "PayPal email is required."
        )

    existing = []

    if wallet.saved_paypals:
        existing = [
            item.strip()
            for item in wallet.saved_paypals.split(",")
            if item.strip()
        ]

    if email not in existing:
        existing.append(email)

    wallet.saved_paypals = ", ".join(existing)

    wallet.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "savedPaypals": existing
    }


# ==========================================================
# DELETE PAYPAL
# ==========================================================

@frappe.whitelist()
def delete_paypal(email):

    wallet = _get_or_create_wallet()

    email = (email or "").strip()

    existing = []

    if wallet.saved_paypals:
        existing = [
            item.strip()
            for item in wallet.saved_paypals.split(",")
            if item.strip()
        ]

    existing = [
        item
        for item in existing
        if item != email
    ]

    wallet.saved_paypals = ", ".join(existing)

    wallet.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "savedPaypals": existing
    }