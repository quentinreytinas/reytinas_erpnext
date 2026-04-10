from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Any

import frappe


def now_utc() -> datetime:
    return datetime.utcnow()


def get_site_url() -> str:
    return frappe.utils.get_url().rstrip("/")


def build_callback_url() -> str:
    return f"{get_site_url()}/api/method/reytinas_erpnext.enablebanking.api.enablebanking_callback"


def generate_state_token() -> str:
    return secrets.token_urlsafe(32)


def normalize_iban(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def coerce_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    if not text:
        return None

    for separator in ("T", " "):
        if separator in text:
            text = text.split(separator, 1)[0]
            break

    return frappe.utils.getdate(text)


def pick_transaction_date(transaction: dict[str, Any]) -> date | None:
    for key in ("booking_date", "bookingDate", "value_date", "valueDate"):
        parsed = coerce_date(transaction.get(key))
        if parsed:
            return parsed
    return None


def compute_transaction_key(link_name: str, transaction: dict[str, Any]) -> str:
    candidates = [
        transaction.get("entry_reference"),
        transaction.get("entryReference"),
        transaction.get("transaction_id"),
        transaction.get("transactionId"),
        transaction.get("internal_transaction_id"),
        transaction.get("internalTransactionId"),
    ]
    for candidate in candidates:
        if candidate:
            return str(candidate)

    amount = extract_amount(transaction) or 0
    booking_date = pick_transaction_date(transaction)
    remittance = extract_description(transaction)
    raw = f"{link_name}|{booking_date or ''}|{amount}|{remittance}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def extract_amount(transaction: dict[str, Any]) -> float:
    amount_block = (
        transaction.get("transaction_amount")
        or transaction.get("transactionAmount")
        or {}
    )
    raw_amount = amount_block.get("amount") or transaction.get("amount")
    try:
        return abs(float(raw_amount))
    except (TypeError, ValueError):
        return 0.0


def extract_currency(transaction: dict[str, Any], fallback: str | None = None) -> str | None:
    amount_block = (
        transaction.get("transaction_amount")
        or transaction.get("transactionAmount")
        or {}
    )
    return amount_block.get("currency") or transaction.get("currency") or fallback


def extract_description(transaction: dict[str, Any]) -> str:
    parts = [
        transaction.get("remittance_information_unstructured"),
        transaction.get("remittanceInformationUnstructured"),
        transaction.get("additional_information"),
        transaction.get("additionalInformation"),
        transaction.get("reference_number"),
        transaction.get("referenceNumber"),
    ]
    values = [str(part).strip() for part in parts if part]
    return " | ".join(dict.fromkeys(values))


def extract_credit_debit_indicator(transaction: dict[str, Any]) -> str:
    return str(
        transaction.get("credit_debit_indicator")
        or transaction.get("creditDebitIndicator")
        or ""
    ).upper()


def default_date_from(sync_days_back: int | None) -> str:
    days = int(sync_days_back or 30)
    return (date.today() - timedelta(days=days)).isoformat()

