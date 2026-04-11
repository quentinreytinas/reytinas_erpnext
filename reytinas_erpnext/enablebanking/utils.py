from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

import frappe


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_db() -> datetime:
    return frappe.utils.now_datetime()


def to_db_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return frappe.utils.get_datetime(text)

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


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
    remittance_lines = extract_remittance_lines(transaction)
    cleaned = _clean_wise_description(remittance_lines)
    if cleaned:
        return cleaned

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


def extract_remittance_lines(transaction: dict[str, Any]) -> list[str]:
    values: list[str] = []
    raw = transaction.get("remittance_information") or transaction.get("remittanceInformation")
    if isinstance(raw, list):
        for item in raw:
            text = str(item).strip()
            if text:
                values.append(text)
    elif raw:
        text = str(raw).strip()
        if text:
            values.append(text)

    for key in (
        "remittance_information_unstructured",
        "remittanceInformationUnstructured",
        "additional_information",
        "additionalInformation",
    ):
        value = transaction.get(key)
        if value:
            text = str(value).strip()
            if text:
                values.append(text)

    return list(dict.fromkeys(values))


def extract_counterparty_name(transaction: dict[str, Any]) -> str:
    parties = [
        transaction.get("counterparty_name"),
        transaction.get("counterpartyName"),
        transaction.get("debtor_name"),
        transaction.get("debtorName"),
        transaction.get("creditor_name"),
        transaction.get("creditorName"),
    ]
    for value in parties:
        if value:
            return str(value).strip()

    for party_key in ("debtor", "creditor"):
        party = transaction.get(party_key)
        if isinstance(party, dict) and party.get("name"):
            return str(party["name"]).strip()

    remittance_lines = extract_remittance_lines(transaction)
    for line in remittance_lines:
        lowered = line.lower()
        if lowered.startswith("sent money to "):
            return line[14:].strip()
        if " issued by " in lowered:
            return re.split(r" issued by ", line, flags=re.IGNORECASE)[-1].strip()
    return ""


def _clean_wise_description(lines: list[str]) -> str:
    if not lines:
        return ""

    for line in lines:
        lowered = line.lower()
        if lowered.startswith("card transaction of ") and " issued by " in lowered:
            merchant = re.split(r" issued by ", line, flags=re.IGNORECASE)[-1].strip()
            if merchant:
                return f"Card purchase - {merchant}"
        if lowered.startswith("sent money to "):
            recipient = line[14:].strip()
            if recipient:
                return f"Transfer sent - {recipient}"
        if lowered == "cashback":
            return "Cashback"

    non_code_lines = [
        line
        for line in lines
        if not re.match(r"^[A-Z_]+-\d", line)
        and not re.match(r"^\d+\.[A-Z_]+-\d", line)
    ]
    if non_code_lines:
        return non_code_lines[0]
    return lines[0]


def extract_credit_debit_indicator(transaction: dict[str, Any]) -> str:
    return str(
        transaction.get("credit_debit_indicator")
        or transaction.get("creditDebitIndicator")
        or ""
    ).upper()


def default_date_from(sync_days_back: int | None) -> str:
    days = int(sync_days_back or 30)
    return (date.today() - timedelta(days=days)).isoformat()
