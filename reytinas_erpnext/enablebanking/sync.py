from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from reytinas_erpnext.enablebanking.client import EnableBankingClient
from reytinas_erpnext.enablebanking.utils import (
    compute_transaction_key,
    default_date_from,
    extract_amount,
    extract_credit_debit_indicator,
    extract_currency,
    extract_description,
    normalize_iban,
    now_utc,
    pick_transaction_date,
)


def get_settings():
    settings = frappe.get_single("EnableBanking Settings")
    settings.ensure_ready()
    return settings


def get_client() -> EnableBankingClient:
    return EnableBankingClient(get_settings())


def sync_all_links() -> None:
    links = frappe.get_all(
        "EnableBanking Account Link",
        filters={"enabled": 1, "status": "Active"},
        pluck="name",
    )
    for link_name in links:
        try:
            sync_link(link_name)
        except Exception:
            frappe.log_error(
                title=_("EnableBanking sync failed"),
                message=frappe.get_traceback(),
            )


def disable_expired_links() -> None:
    links = frappe.get_all(
        "EnableBanking Account Link",
        filters={"enabled": 1, "status": "Active"},
        fields=["name", "session_valid_until"],
    )
    now = now_utc()
    for row in links:
        valid_until = row.get("session_valid_until")
        if valid_until and valid_until <= now:
            doc = frappe.get_doc("EnableBanking Account Link", row["name"])
            doc.status = "Expired"
            doc.enabled = 0
            doc.save(ignore_permissions=True)
    if links:
        frappe.db.commit()


@frappe.whitelist()
def sync_link(link_name: str) -> dict[str, Any]:
    link = frappe.get_doc("EnableBanking Account Link", link_name)
    if not link.enabled:
        frappe.throw(_("EnableBanking link {0} is disabled").format(link.name))
    if not link.account_uid:
        frappe.throw(_("EnableBanking link {0} has no linked account uid").format(link.name))

    settings = get_settings()
    client = EnableBankingClient(settings)
    imported = import_transactions(client, link)
    link.last_sync_at = now_utc()
    link.last_error_code = None
    link.last_error_message = None
    if imported["latest_booking_date"]:
        link.last_transaction_date = imported["latest_booking_date"]
    link.save(ignore_permissions=True)

    bank_account = frappe.get_doc("Bank Account", link.bank_account)
    bank_account.integration_id = link.identification_hash or link.account_uid
    bank_account.last_integration_date = frappe.utils.nowdate()
    bank_account.save(ignore_permissions=True)
    frappe.db.commit()
    return imported


def import_transactions(client: EnableBankingClient, link) -> dict[str, Any]:
    date_from = (
        str(link.last_transaction_date)
        if link.last_transaction_date
        else default_date_from(get_settings().sync_days_back)
    )
    continuation_key = None
    imported = 0
    latest_booking_date = None

    while True:
        payload = client.get_transactions(
            link.account_uid,
            date_from=date_from,
            continuation_key=continuation_key,
        )
        transactions = payload.get("transactions") or payload.get("entries") or []
        for transaction in transactions:
            was_created, booking_date = create_bank_transaction(link, transaction)
            if was_created:
                imported += 1
            if booking_date and (latest_booking_date is None or booking_date > latest_booking_date):
                latest_booking_date = booking_date

        continuation_key = payload.get("continuation_key") or payload.get("continuationKey")
        if not continuation_key:
            break

    return {"imported_count": imported, "latest_booking_date": latest_booking_date}


def create_bank_transaction(link, transaction: dict[str, Any]) -> tuple[bool, Any]:
    transaction_key = compute_transaction_key(link.name, transaction)
    if frappe.db.exists(
        "Bank Transaction",
        {"bank_account": link.bank_account, "transaction_id": transaction_key},
    ):
        return False, pick_transaction_date(transaction)

    indicator = extract_credit_debit_indicator(transaction)
    amount = extract_amount(transaction)
    booking_date = pick_transaction_date(transaction) or frappe.utils.getdate()
    currency = extract_currency(transaction, link.currency)
    description = extract_description(transaction)
    reference_number = (
        transaction.get("entry_reference")
        or transaction.get("entryReference")
        or transaction.get("reference_number")
        or transaction.get("referenceNumber")
    )
    bank_party_iban = normalize_iban(
        transaction.get("counterparty_iban")
        or transaction.get("counterpartyIban")
        or transaction.get("debtor_account", {}).get("iban")
        or transaction.get("creditor_account", {}).get("iban")
    )
    bank_party_name = (
        transaction.get("counterparty_name")
        or transaction.get("counterpartyName")
        or transaction.get("debtor_name")
        or transaction.get("debtorName")
        or transaction.get("creditor_name")
        or transaction.get("creditorName")
    )

    doc = frappe.get_doc(
        {
            "doctype": "Bank Transaction",
            "date": booking_date,
            "bank_account": link.bank_account,
            "company": link.company,
            "currency": currency,
            "description": description,
            "reference_number": reference_number,
            "transaction_id": transaction_key,
            "transaction_type": transaction.get("proprietary_bank_transaction_code")
            or transaction.get("proprietaryBankTransactionCode")
            or "EnableBanking Import",
            "bank_party_name": bank_party_name,
            "bank_party_iban": bank_party_iban,
        }
    )
    if indicator == "CRDT":
        doc.deposit = amount
    else:
        doc.withdrawal = amount

    fee_amount = transaction.get("fee_amount") or transaction.get("feeAmount")
    try:
        if fee_amount:
            doc.included_fee = abs(float(fee_amount))
    except (TypeError, ValueError):
        pass

    doc.insert(ignore_permissions=True)
    doc.submit()
    return True, booking_date

