from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from reytinas_erpnext.enablebanking.client import EnableBankingClient
from reytinas_erpnext.enablebanking.sync import sync_link
from reytinas_erpnext.enablebanking.utils import (
    build_callback_url,
    generate_state_token,
    get_site_url,
    normalize_iban,
)


def get_settings():
    settings = frappe.get_single("EnableBanking Settings")
    settings.ensure_ready()
    return settings


@frappe.whitelist()
def get_aspsps(country: str = "FR", psu_type: str = "business") -> list[dict[str, Any]]:
    client = EnableBankingClient(get_settings())
    payload = client.get_aspsps(country=country, psu_type=psu_type)
    return payload.get("aspsps") or payload.get("results") or []


@frappe.whitelist()
def start_authorization(
    bank_account: str,
    aspsp_name: str,
    aspsp_country: str = "FR",
    aspsp_id: str | None = None,
    company: str | None = None,
    psu_type: str = "business",
) -> dict[str, Any]:
    settings = get_settings()
    client = EnableBankingClient(settings)

    bank_account_doc = frappe.get_doc("Bank Account", bank_account)
    company_name = company or bank_account_doc.company
    if not company_name:
        frappe.throw(_("Bank Account {0} must be linked to a company").format(bank_account))

    existing_link = frappe.db.get_value(
        "EnableBanking Account Link",
        {"bank_account": bank_account, "company": company_name},
        "name",
    )
    link = (
        frappe.get_doc("EnableBanking Account Link", existing_link)
        if existing_link
        else frappe.new_doc("EnableBanking Account Link")
    )

    state = generate_state_token()
    link.company = company_name
    link.bank_account = bank_account
    link.aspsp_name = aspsp_name
    link.aspsp_country = aspsp_country
    link.aspsp_id = aspsp_id
    link.psu_type = psu_type
    link.authorization_state = state
    link.status = "Pending Authorization"
    link.enabled = 1
    link.save(ignore_permissions=True)

    valid_until = settings.get_default_valid_until_iso()
    payload = {
        "aspsp": {
            "name": aspsp_name,
            "country": aspsp_country,
        },
        "state": state,
        "redirect_url": settings.redirect_url or build_callback_url(),
        "psu_type": psu_type,
        "access": {"valid_until": valid_until},
    }
    if aspsp_id:
        payload["aspsp"]["uid"] = aspsp_id

    result = client.start_authorization(payload)
    authorization_url = (
        result.get("url")
        or result.get("authorization_url")
        or result.get("authorizationUrl")
    )
    if not authorization_url:
        frappe.throw(_("EnableBanking did not return an authorization URL"))

    link.authorization_url = authorization_url
    link.save(ignore_permissions=True)
    frappe.db.commit()
    return {"link_name": link.name, "authorization_url": authorization_url}


@frappe.whitelist(allow_guest=True)
def enablebanking_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        frappe.throw(_("EnableBanking authorization failed: {0}").format(error))
    if not code or not state:
        frappe.throw(_("EnableBanking callback is missing code or state"))

    link_name = frappe.db.get_value(
        "EnableBanking Account Link",
        {"authorization_state": state},
        "name",
    )
    if not link_name:
        frappe.throw(_("Unknown EnableBanking authorization state"))

    link = frappe.get_doc("EnableBanking Account Link", link_name)
    settings = get_settings()
    client = EnableBankingClient(settings)
    session_data = client.create_session(code)

    session = session_data.get("session") or session_data
    accounts_payload = client.get_accounts(session["uid"])
    accounts = accounts_payload.get("accounts") or accounts_payload.get("results") or []
    if not accounts:
        frappe.throw(_("EnableBanking returned no bank accounts for this authorization"))

    account = _match_account(link.bank_account, accounts)
    if not account:
        frappe.throw(
            _("No EnableBanking account matched ERPNext bank account {0}").format(link.bank_account)
        )

    link.session_id = session["uid"]
    link.session_valid_until = session.get("valid_until") or session.get("validUntil")
    link.account_uid = account.get("uid")
    link.identification_hash = account.get("identification_hash") or account.get("identificationHash")
    link.account_iban = normalize_iban(
        account.get("iban") or account.get("account_number") or account.get("accountNumber")
    )
    link.account_name = account.get("name") or account.get("display_name") or account.get("displayName")
    link.currency = account.get("currency")
    link.status = "Active"
    link.authorization_state = None
    link.authorization_url = None
    link.enabled = 1
    link.save(ignore_permissions=True)
    frappe.db.commit()

    sync_link(link.name)
    redirect_to = f"{get_site_url()}/app/enablebanking-account-link/{link.name}"
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = redirect_to


def _match_account(bank_account_name: str, accounts: list[dict[str, Any]]) -> dict[str, Any] | None:
    bank_account = frappe.get_doc("Bank Account", bank_account_name)
    expected_iban = normalize_iban(bank_account.iban)
    expected_number = normalize_iban(bank_account.bank_account_no)

    for account in accounts:
        account_iban = normalize_iban(
            account.get("iban") or account.get("account_number") or account.get("accountNumber")
        )
        if expected_iban and account_iban == expected_iban:
            return account
        if expected_number and account_iban == expected_number:
            return account

    if len(accounts) == 1:
        return accounts[0]
    return None

