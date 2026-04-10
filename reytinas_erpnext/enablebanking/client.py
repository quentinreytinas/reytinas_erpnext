from __future__ import annotations

from typing import Any

import frappe
import jwt
import requests
from frappe import _

from reytinas_erpnext.enablebanking.utils import now_utc


class EnableBankingClient:
    def __init__(self, settings):
        self.settings = settings
        self.base_url = settings.api_base_url.rstrip("/")
        self.timeout = int(settings.request_timeout or 30)

    def _build_headers(self) -> dict[str, str]:
        issued_at = int(now_utc().timestamp())
        payload = {
            "iss": self.settings.application_id,
            "sub": self.settings.application_id,
            "aud": self.base_url,
            "iat": issued_at,
            "nbf": issued_at,
            "exp": issued_at + 300,
        }
        headers = {"kid": self.settings.key_id, "typ": "JWT"}
        token = jwt.encode(
            payload,
            self.settings.get_private_key(),
            algorithm="RS256",
            headers=headers,
        )
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.request(
            method=method,
            url=url,
            headers=self._build_headers(),
            params=params,
            json=json,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            message = response.text
            frappe.log_error(
                title=_("EnableBanking API Error"),
                message=f"{method} {url}\n{response.status_code}\n{message}",
            )
            frappe.throw(
                _("EnableBanking request failed ({0}): {1}").format(
                    response.status_code, message
                )
            )

        if not response.content:
            return {}
        return response.json()

    def get_aspsps(
        self, *, country: str | None = None, psu_type: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if country:
            params["country"] = country
        if psu_type:
            params["psu_type"] = psu_type
        return self._request("GET", "/aspsps", params=params)

    def start_authorization(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/auth", json=payload)

    def create_session(self, code: str) -> dict[str, Any]:
        return self._request("POST", "/sessions", json={"code": code})

    def get_accounts(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/sessions/{session_id}/accounts")

    def get_transactions(
        self,
        account_uid: str,
        *,
        date_from: str | None = None,
        continuation_key: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if date_from:
            params["date_from"] = date_from
        if continuation_key:
            params["continuation_key"] = continuation_key
        return self._request("GET", f"/accounts/{account_uid}/transactions", params=params)

