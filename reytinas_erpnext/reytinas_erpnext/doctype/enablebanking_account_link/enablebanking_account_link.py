from __future__ import annotations

import frappe
from frappe.model.document import Document


class EnableBankingAccountLink(Document):
    def validate(self):
        if self.bank_account and not self.company:
            self.company = frappe.db.get_value("Bank Account", self.bank_account, "company")

