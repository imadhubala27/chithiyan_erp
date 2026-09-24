# Copyright (c) 2026, techpanjab.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WalletsandSavedCards(Document):
    pass


# ==========================================================
# CURRENT USER
# ==========================================================

def _get_current_user():
    user = frappe.session.user

    if not user or user == "Guest":
        frappe.throw("Please login first.")

    return user


# ==========================================================
# GET / CREATE WALLET
# ==========================================================

def _get_or_create_wallet():
    user = _get_current_user()

    # Find wallet by document owner
    wallet_name = frappe.db.get_value(
        "Wallets and Saved Cards",
        {"owner": user},
        "name",
    )

    if wallet_name:
        return frappe.get_doc(
            "Wallets and Saved Cards",
            wallet_name,
        )

    # Create new wallet
    wallet = frappe.new_doc(
        "Wallets and Saved Cards"
    )

    wallet.wallet_balance = 0
    wallet.wallet_active = 0

    wallet.insert(
        ignore_permissions=True
    )

    return wallet


# ==========================================================
# HELPERS
# ==========================================================

def _parse_list(value):
    if not value:
        return []

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def _join_list(items):
    return ", ".join(
        item.strip()
        for item in items
        if item and item.strip()
    )


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

    return {
        "id": wallet.name,
        "walletBalance": float(
            wallet.wallet_balance or 0
        ),
        "walletActive": bool(
            wallet.wallet_active
        ),
        "savedCards": cards,
        "savedUpis": _parse_list(
            wallet.saved_upis
        ),
        "savedPaypals": _parse_list(
            wallet.saved_paypals
        ),
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

    current_balance = frappe.utils.flt(
        wallet.wallet_balance
    )

    wallet.wallet_balance = (
        current_balance + amount
    )

    wallet.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "walletBalance": float(
            wallet.wallet_balance
        )
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

    card_number = (
        card_number or ""
    ).strip()

    card_name = (
        card_name or ""
    ).strip()

    expiry = (
        expiry or ""
    ).strip()

    holder = (
        holder or ""
    ).strip()

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

    # Never store an unmasked card number
    digits = "".join(
        char
        for char in card_number
        if char.isdigit()
    )

    if len(digits) == 16:
        card_number = (
            "**** **** **** "
            + digits[-4:]
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

    card = next(
        (
            row
            for row in wallet.saved_cards or []
            if row.name == card_id
        ),
        None,
    )

    if not card:
        frappe.throw(
            "Saved card not found."
        )

    card_number = (
        card_number or ""
    ).strip()

    digits = "".join(
        char
        for char in card_number
        if char.isdigit()
    )

    if len(digits) == 16:
        card_number = (
            "**** **** **** "
            + digits[-4:]
        )

    card.card_number = card_number
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

    card = next(
        (
            row
            for row in wallet.saved_cards or []
            if row.name == card_id
        ),
        None,
    )

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

    upi = (
        upi or ""
    ).strip().lower()

    if not upi:
        frappe.throw(
            "UPI ID is required."
        )

    existing = _parse_list(
        wallet.saved_upis
    )

    if upi not in existing:
        existing.append(upi)

    wallet.saved_upis = _join_list(
        existing
    )

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

    upi = (
        upi or ""
    ).strip().lower()

    existing = _parse_list(
        wallet.saved_upis
    )

    existing = [
        item
        for item in existing
        if item.lower() != upi
    ]

    wallet.saved_upis = _join_list(
        existing
    )

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

    email = (
        email or ""
    ).strip().lower()

    if not email:
        frappe.throw(
            "PayPal email is required."
        )

    existing = _parse_list(
        wallet.saved_paypals
    )

    if email not in existing:
        existing.append(email)

    wallet.saved_paypals = _join_list(
        existing
    )

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

    email = (
        email or ""
    ).strip().lower()

    existing = _parse_list(
        wallet.saved_paypals
    )

    existing = [
        item
        for item in existing
        if item.lower() != email
    ]

    wallet.saved_paypals = _join_list(
        existing
    )

    wallet.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "savedPaypals": existing
    }