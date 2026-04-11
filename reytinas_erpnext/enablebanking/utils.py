from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

import frappe

CARD_REFERENCE_PATTERN = re.compile(r"\ACARD-\d+\Z", re.IGNORECASE)
REFERENCE_PATTERNS = (
    CARD_REFERENCE_PATTERN,
    re.compile(r"\A[A-Z0-9]{10,}\Z"),
    re.compile(r"\A[A-Z0-9]+(?:[-_][A-Z0-9]+){2,}\Z"),
    re.compile(r"\A\d+\.[A-Z_]+-\d+\Z"),
)
REMITTANCE_ENTITY_PATTERNS = (
    re.compile(r"\bissued by\s+(.+)\Z", re.IGNORECASE),
    re.compile(r"\bpaid to\s+(.+)\Z", re.IGNORECASE),
    re.compile(r"\bpurchase at\s+(.+)\Z", re.IGNORECASE),
    re.compile(r"\bsent money to\s+(.+)\Z", re.IGNORECASE),
    re.compile(r"\breceived money from\s+(.+)\Z", re.IGNORECASE),
)
REMITTANCE_TRAILING_PATTERNS = (
    re.compile(r"\s+CARTE\s+\d+\Z", re.IGNORECASE),
    re.compile(r"\s+CARD\s+\d+\Z", re.IGNORECASE),
)
REMITTANCE_REFERENCE_SUFFIX_PATTERNS = (
    re.compile(r"\s+with\s+reference\Z", re.IGNORECASE),
    re.compile(r"\s+avec\s+r[eé]f[eé]rence\Z", re.IGNORECASE),
)
CUSTOMER_REFERENCE_PATTERNS = (
    re.compile(r"(?:^|[\s-])r[eé]f[eé]rence\s+client\b", re.IGNORECASE),
    re.compile(r"(?:^|[\s-])ref(?:erence)?\s+client\b", re.IGNORECASE),
    re.compile(r"\bclient\s+reference\b", re.IGNORECASE),
)
GENERIC_CARD_PAYMENT_PATTERNS = (
    re.compile(r"\APAIEMENT\s+(?:CB|PSC)\b", re.IGNORECASE),
    re.compile(r"\ACARD\s+PAYMENT\b", re.IGNORECASE),
)
PERSONAL_COUNTERPARTY_PATTERNS = (
    re.compile(r"\A(?:M|MME|MLLE|MONSIEUR|MADAME|MADEMOISELLE)\b", re.IGNORECASE),
    re.compile(r"\A(?:M|MME)\s+OU\s+(?:M|MME)\b", re.IGNORECASE),
    re.compile(r"\A(?:MR|MRS|MS)\b", re.IGNORECASE),
)
EXPANDED_BANKING_ACTION_PATTERNS = (
    re.compile(r"\bpr[eé]l[eè]vement\b", re.IGNORECASE),
    re.compile(r"\bvirement\b", re.IGNORECASE),
)
ABBREVIATED_BANKING_HEADER_PATTERNS = (
    re.compile(r"\A(?:PRLV|VIR)\b", re.IGNORECASE),
)
WITHDRAWAL_DESCRIPTION_PATTERN = re.compile(
    r"\A(?:RETRAIT|WITHDRAWAL|ATM)\b.*?\b\d{4}\s+(.+)\Z",
    re.IGNORECASE,
)


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
    description = (
        transaction.get("description")
        or transaction.get("transaction_description")
        or transaction.get("transactionDescription")
    )
    counterparty = _select_counterparty_name(transaction)
    bank_transaction_description = _extract_bank_transaction_description(transaction)
    remittance_name = _select_remittance_name(
        remittance_lines,
        excluding=[description, counterparty],
    )
    selected = _resolve_transaction_name(
        description=description,
        remittance_name=remittance_name,
        counterparty=counterparty,
        bank_transaction_description=bank_transaction_description,
        credit_debit_indicator=extract_credit_debit_indicator(transaction),
    )
    if selected:
        return selected

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
    remittance_lines = extract_remittance_lines(transaction)
    counterparty = _select_counterparty_name(transaction)
    remittance_name = _select_remittance_name(remittance_lines, excluding=[counterparty])
    if remittance_name and (
        not counterparty
        or _is_card_reference(counterparty)
        or _looks_personal(counterparty)
    ):
        return remittance_name
    return counterparty


def extract_credit_debit_indicator(transaction: dict[str, Any]) -> str:
    return str(
        transaction.get("credit_debit_indicator")
        or transaction.get("creditDebitIndicator")
        or ""
    ).upper()


def default_date_from(sync_days_back: int | None) -> str:
    days = int(sync_days_back or 30)
    return (date.today() - timedelta(days=days)).isoformat()


def _select_counterparty_name(transaction: dict[str, Any]) -> str:
    indicator = extract_credit_debit_indicator(transaction)
    candidates: list[Any] = [
        transaction.get("counterparty_name"),
        transaction.get("counterpartyName"),
    ]
    if indicator == "CRDT":
        candidates.extend(
            [
                transaction.get("debtor_name"),
                transaction.get("debtorName"),
                _extract_party_name(transaction.get("debtor")),
            ]
        )
    else:
        candidates.extend(
            [
                transaction.get("creditor_name"),
                transaction.get("creditorName"),
                _extract_party_name(transaction.get("creditor")),
            ]
        )

    if indicator == "CRDT":
        candidates.extend(
            [
                transaction.get("creditor_name"),
                transaction.get("creditorName"),
                _extract_party_name(transaction.get("creditor")),
            ]
        )
    else:
        candidates.extend(
            [
                transaction.get("debtor_name"),
                transaction.get("debtorName"),
                _extract_party_name(transaction.get("debtor")),
            ]
        )

    for value in candidates:
        text = str(value).strip() if value else ""
        if text:
            return text
    return ""


def _extract_party_name(value: Any) -> str:
    return str(value.get("name")).strip() if isinstance(value, dict) and value.get("name") else ""


def _extract_bank_transaction_description(transaction: dict[str, Any]) -> str:
    return str(
        (transaction.get("bank_transaction_code") or {}).get("description")
        or (transaction.get("bankTransactionCode") or {}).get("description")
        or ""
    ).strip()


def _resolve_transaction_name(
    *,
    description: Any,
    remittance_name: str,
    counterparty: str,
    bank_transaction_description: str,
    credit_debit_indicator: str,
) -> str:
    description_text = str(description).strip() if description else ""
    if description_text:
        withdrawal_name = _withdrawal_name_candidate(description_text, remittance_name)
        if withdrawal_name:
            return withdrawal_name
        if _prefer_remittance_name(description_text, remittance_name):
            return remittance_name
        return description_text

    if (
        remittance_name
        and _looks_personal(counterparty)
        and not _is_reference_like(remittance_name)
        and not _looks_like_customer_reference(remittance_name)
    ):
        return remittance_name

    if counterparty and not _is_card_reference(counterparty):
        return counterparty

    if remittance_name and (
        _prefer_remittance_name(bank_transaction_description, remittance_name)
        or (_is_card_reference(counterparty) and not _is_reference_like(remittance_name))
    ):
        return remittance_name

    if bank_transaction_description:
        return bank_transaction_description
    if remittance_name:
        return remittance_name
    if credit_debit_indicator == "CRDT":
        return "Incoming Transfer"
    return "Outgoing Transfer"


def _select_remittance_name(lines: list[str], excluding: list[Any] | None = None) -> str:
    excluded = {
        str(value).strip().lower()
        for value in (excluding or [])
        if value and str(value).strip()
    }
    candidates = []
    for line in lines:
        candidate = _extract_remittance_name(line)
        if candidate and candidate.lower() not in excluded:
            candidates.append(candidate)

    if not candidates:
        return ""

    pool = [value for value in candidates if not _is_reference_like(value) and not _is_generic_card_header(value)]
    if not pool:
        pool = candidates

    non_customer = [value for value in pool if not _looks_like_customer_reference(value)]
    if non_customer:
        pool = non_customer

    descriptive = [value for value in pool if _is_descriptive_phrase(value)]
    if descriptive:
        pool = descriptive

    return max(pool, key=_remittance_candidate_score)


def _extract_remittance_name(line: str) -> str:
    text = _extract_entity_from_remittance_line(line)
    for pattern in REMITTANCE_TRAILING_PATTERNS:
        text = pattern.sub("", text)
    return re.sub(r"\s+", " ", text).strip()[:200]


def _extract_entity_from_remittance_line(line: str) -> str:
    text = str(line).strip()
    if not text:
        return ""
    for pattern in REMITTANCE_ENTITY_PATTERNS:
        match = pattern.search(text)
        if match and match.group(1):
            return _remove_reference_suffix(match.group(1).strip())
    return _remove_reference_suffix(text)


def _remove_reference_suffix(text: str) -> str:
    cleaned = text
    for pattern in REMITTANCE_REFERENCE_SUFFIX_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    return cleaned.strip()


def _prefer_remittance_name(description: str, remittance_name: str) -> bool:
    if not description or not remittance_name:
        return False
    if description.strip().lower() == remittance_name.strip().lower():
        return False
    if _looks_like_customer_reference(description) and not _is_reference_like(remittance_name):
        return True
    if _is_generic_card_header(description):
        return True
    if _is_technical_description(description) and _is_descriptive_phrase(remittance_name):
        return True
    if _is_descriptive_phrase(remittance_name) and (
        _has_expanded_banking_action(remittance_name) or _has_abbreviated_banking_header(description)
    ):
        return True
    return (
        _informativeness_score(remittance_name) >= _informativeness_score(description) + 4
        and _technicality_score(remittance_name) <= _technicality_score(description)
    )


def _remittance_candidate_score(value: str) -> int:
    score = _informativeness_score(value) - _technicality_score(value)
    if _is_descriptive_phrase(value):
        score += 6
    if _has_expanded_banking_action(value):
        score += 3
    if _has_abbreviated_banking_header(value):
        score -= 2
    return score


def _is_card_reference(value: str) -> bool:
    return bool(value and CARD_REFERENCE_PATTERN.match(value.strip()))


def _is_reference_like(value: str) -> bool:
    text = value.strip() if value else ""
    return any(pattern.match(text) for pattern in REFERENCE_PATTERNS) if text else False


def _looks_like_customer_reference(value: str) -> bool:
    text = value.strip() if value else ""
    return any(pattern.search(text) for pattern in CUSTOMER_REFERENCE_PATTERNS) if text else False


def _is_generic_card_header(value: str) -> bool:
    text = value.strip() if value else ""
    return any(pattern.match(text) for pattern in GENERIC_CARD_PAYMENT_PATTERNS) if text else False


def _has_expanded_banking_action(value: str) -> bool:
    text = value.strip() if value else ""
    return any(pattern.search(text) for pattern in EXPANDED_BANKING_ACTION_PATTERNS) if text else False


def _has_abbreviated_banking_header(value: str) -> bool:
    text = value.strip() if value else ""
    return any(pattern.match(text) for pattern in ABBREVIATED_BANKING_HEADER_PATTERNS) if text else False


def _looks_personal(value: str) -> bool:
    text = value.strip() if value else ""
    return any(pattern.match(text) for pattern in PERSONAL_COUNTERPARTY_PATTERNS) if text else False


def _withdrawal_name_candidate(description: str, remittance_name: str) -> str:
    if not description or not remittance_name:
        return ""

    match = WITHDRAWAL_DESCRIPTION_PATTERN.match(description.strip())
    if not match:
        return ""

    location = match.group(1).strip()
    candidate = remittance_name.strip()
    if not location or not candidate:
        return ""
    if re.match(r"\A(?:RETRAIT|WITHDRAWAL|ATM)\b", candidate, re.IGNORECASE):
        return ""
    if _is_reference_like(candidate):
        return ""
    if location.lower() in candidate.lower():
        return ""
    if _technicality_score(candidate) >= 7:
        return ""

    prefix = description.strip().split()[0].upper()
    return f"{prefix} {location} {candidate}".strip()


def _is_descriptive_phrase(value: str) -> bool:
    words = [
        re.sub(r"[^A-Za-z]", "", word.lower())
        for word in re.split(r"\s+", value.strip())
    ] if value else []
    cleaned = [word for word in words if word]
    return len(set(cleaned)) >= 2


def _is_technical_description(value: str) -> bool:
    text = value.strip() if value else ""
    if not text:
        return False
    words = text.split()
    alpha_words = [
        re.sub(r"[^A-Za-z]", "", word).lower()
        for word in words
    ]
    alpha_words = [word for word in alpha_words if word]
    digit_count = len(re.findall(r"\d", text))
    uppercase_words = sum(1 for word in words if re.match(r"^[A-Z\d\W]+$", word))
    uppercase_ratio = (uppercase_words / len(words)) if words else 0.0
    return any(pattern.match(text) for pattern in REFERENCE_PATTERNS) or (
        len(set(alpha_words)) <= 1 and digit_count >= 4 and uppercase_ratio >= 0.5
    )


def _informativeness_score(value: str) -> int:
    text = value.strip() if value else ""
    if not text:
        return 0
    words = text.split()
    alpha_words = [word for word in words if re.search(r"[A-Za-z]", word)]
    unique_alpha_words = {
        re.sub(r"[^A-Za-z]", "", word).lower()
        for word in alpha_words
        if re.sub(r"[^A-Za-z]", "", word)
    }
    digit_count = len(re.findall(r"\d", text))
    symbol_count = len(re.findall(r"[^\w\s]", text, re.UNICODE))
    mixed_case_bonus = 2 if re.search(r"[A-Z]", text) and re.search(r"[a-z]", text) else 0
    return (len(alpha_words) * 2) + len(unique_alpha_words) + mixed_case_bonus - digit_count - (symbol_count // 2)


def _technicality_score(value: str) -> int:
    text = value.strip() if value else ""
    if not text:
        return 0
    words = text.split()
    uppercase_words = sum(1 for word in words if re.match(r"^[A-Z\d\W]+$", word))
    uppercase_ratio = (uppercase_words / len(words)) if words else 0.0
    digit_count = len(re.findall(r"\d", text))
    symbol_count = len(re.findall(r"[^\w\s]", text, re.UNICODE))
    date_token_count = len(re.findall(r"\b\d{1,4}[/-]\d{1,4}(?:[/-]\d{1,4})?\b", text))

    score = 0
    if _is_reference_like(text):
        score += 3
    if uppercase_ratio >= 0.8 and len(words) >= 3:
        score += 2
    score += digit_count
    score += symbol_count // 2
    score += date_token_count * 2
    return score
