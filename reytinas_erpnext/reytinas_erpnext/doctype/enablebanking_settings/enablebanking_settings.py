from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from reytinas_erpnext.enablebanking.utils import build_callback_url, now_utc


class EnableBankingSettings(Document):
    def validate(self):
        self.redirect_url = build_callback_url()

    def ensure_ready(self) -> None:
        required_fields = {
            "enabled": self.enabled,
            "api_base_url": self.api_base_url,
            "application_id": self.application_id,
            "key_id": self.key_id,
        }
        missing = [field for field, value in required_fields.items() if not value]
        if missing:
            frappe.throw(
                _("EnableBanking Settings is incomplete. Missing: {0}").format(", ".join(missing))
            )
        if not self.get_private_key():
            frappe.throw(_("EnableBanking private key is not configured"))

    def get_private_key(self) -> str:
        return self.get_password("private_key") or ""

    def get_default_valid_until_iso(self) -> str:
        days = int(self.authorization_valid_days or 90)
        valid_until = now_utc() + frappe.utils.timedelta(days=days)
        return valid_until.replace(microsecond=0).isoformat()
