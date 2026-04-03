from __future__ import annotations

import frappe


PRINT_FORMATS = (
    {
        "name": "Reytinas Devis",
        "doc_type": "Quotation",
        "module": "Selling",
    },
    {
        "name": "Reytinas Facture",
        "doc_type": "Sales Invoice",
        "module": "Accounts",
    },
)


PRINT_FORMAT_HTML = """
{% set is_quote = doc.doctype == "Quotation" %}
{% set date_field = "transaction_date" if is_quote else "posting_date" %}
{% set due_field = "valid_till" if is_quote else "due_date" %}
{% set title = "DEVIS" if is_quote else "FACTURE" %}
{% set company = frappe.db.get_value(
  "Company",
  doc.company,
  ["company_name", "company_logo", "tax_id", "email", "phone_no", "website"],
  as_dict=True,
) or {} %}
{% set bank_accounts = frappe.db.get_all(
  "Bank Account",
  filters={"company": doc.company, "is_company_account": 1},
  fields=["bank", "iban", "bank_account_no", "account_name"],
  limit=1,
) %}
{% set bank = bank_accounts[0] if bank_accounts else None %}
{% set siret = "521 301 457 00052" if doc.company == "Quentin Reytinas" else "" %}

<section class="rt-print">
  <header class="rt-header">
    <div class="rt-brand-block">
      <div class="rt-brand-row">
        {% if company.company_logo %}
          <img class="rt-logo" src="{{ frappe.utils.get_url(company.company_logo) }}" alt="{{ doc.company }}">
        {% else %}
          <div class="rt-logo-fallback">{{ doc.company[:2] }}</div>
        {% endif %}
        <div class="rt-company-wrap">
          <div class="rt-company-name">{{ company.company_name or doc.company }}</div>
          {% if doc.company_address_display %}
            <div class="rt-company-address">{{ doc.company_address_display }}</div>
          {% endif %}
        </div>
      </div>
    </div>

    <div class="rt-meta-card">
      <div class="rt-eyebrow">{{ title }}</div>
      <h1 class="rt-doc-name">{{ doc.name }}</h1>
      <div class="rt-meta-row">
        <span>Date</span>
        <strong>{{ doc.get_formatted(date_field) }}</strong>
      </div>
      {% if doc.get(due_field) %}
        <div class="rt-meta-row">
          <span>{{ "Validité" if is_quote else "Échéance" }}</span>
          <strong>{{ doc.get_formatted(due_field) }}</strong>
        </div>
      {% endif %}
      <div class="rt-meta-row">
        <span>Devise</span>
        <strong>{{ doc.currency }}</strong>
      </div>
    </div>
  </header>

  <section class="rt-party-grid">
    <div class="rt-party-card">
      <div class="rt-section-title">Émis par</div>
      <div class="rt-party-name">{{ company.company_name or doc.company }}</div>
      {% if doc.company_address_display %}
        <div class="rt-party-address">{{ doc.company_address_display }}</div>
      {% endif %}
      <div class="rt-party-extra">
        {% if company.email %}
          <div>{{ company.email }}</div>
        {% endif %}
        {% if company.phone_no %}
          <div>{{ company.phone_no }}</div>
        {% endif %}
        {% if company.website %}
          <div>{{ company.website }}</div>
        {% endif %}
      </div>
    </div>

    <div class="rt-party-card">
      <div class="rt-section-title">Client</div>
      <div class="rt-party-name">
        {{ doc.customer_name or doc.party_name or doc.customer or doc.name }}
      </div>
      {% if doc.address_display %}
        <div class="rt-party-address">{{ doc.address_display }}</div>
      {% endif %}
      {% if doc.po_no %}
        <div class="rt-party-ref">Référence commande: {{ doc.po_no }}</div>
      {% endif %}
    </div>
  </section>

  <table class="rt-items">
    <thead>
      <tr>
        <th class="rt-col-idx">#</th>
        <th class="rt-col-desc">Désignation</th>
        <th class="rt-col-qty">Qté</th>
        <th class="rt-col-rate">PU HT</th>
        <th class="rt-col-amount">Montant HT</th>
      </tr>
    </thead>
    <tbody>
      {% for row in doc.items %}
        <tr>
          <td class="rt-idx">{{ row.idx }}</td>
          <td class="rt-desc">
            <div class="rt-item-name">{{ row.item_name or row.item_code }}</div>
            {% if row.description %}
              <div class="rt-item-description">{{ row.description }}</div>
            {% endif %}
          </td>
          <td class="rt-num rt-nowrap">{{ row.qty }} {{ row.uom or row.stock_uom or "" }}</td>
          <td class="rt-num rt-nowrap">{{ row.get_formatted("rate", doc) }}</td>
          <td class="rt-num rt-nowrap">{{ row.get_formatted("amount", doc) }}</td>
        </tr>
      {% endfor %}
    </tbody>
  </table>

  <section class="rt-summary-grid">
    <div class="rt-summary-note-card">
      {% if doc.in_words %}
        <div class="rt-section-title">Montant en toutes lettres</div>
        <div class="rt-in-words">{{ doc.in_words }}</div>
      {% else %}
        <div class="rt-section-title">Règlement</div>
        <div class="rt-summary-note">
          {% if is_quote %}
            Le détail du total apparaît ci-contre. Le devis reste soumis aux conditions indiquées plus bas.
          {% else %}
            Le détail du total apparaît ci-contre. Merci de rappeler la référence de facture lors du règlement.
          {% endif %}
        </div>
      {% endif %}
    </div>

    <div class="rt-totals-card">
      <div class="rt-total-row">
        <span>Total HT</span>
        <strong>{{ doc.get_formatted("net_total") }}</strong>
      </div>
      {% for tax in doc.taxes %}
        {% if tax.tax_amount %}
          <div class="rt-total-row">
            <span>{{ tax.description or "Taxe" }}</span>
            <strong>{{ tax.get_formatted("tax_amount", doc) }}</strong>
          </div>
        {% endif %}
      {% endfor %}
      <div class="rt-grand-total">
        <span>Total TTC</span>
        <strong>{{ doc.get_formatted("grand_total") }}</strong>
      </div>
    </div>
  </section>

  {% if doc.terms %}
    <section class="rt-notes">
      <div class="rt-section-title">Conditions & CGV</div>
      <div class="rt-terms">{{ doc.terms }}</div>
    </section>
  {% endif %}

  <footer class="rt-footer">
    <div class="rt-footer-note">
      {% if is_quote %}
        Merci pour votre confiance. Ce devis reste valable jusqu'à la date indiquée ci-dessus.
      {% else %}
        Merci de rappeler le numéro de facture lors de votre règlement.
      {% endif %}
    </div>
    <div class="rt-footer-legal">
      <span>{{ company.company_name or doc.company }}</span>
      {% if siret %}<span>SIRET {{ siret }}</span>{% endif %}
      {% if company.tax_id %}<span>TVA {{ company.tax_id }}</span>{% endif %}
      {% if bank and (bank.iban or bank.bank_account_no) %}
        <span>{{ bank.bank or "Banque" }} · {{ bank.iban or bank.bank_account_no }}</span>
      {% endif %}
    </div>
  </footer>
</section>
"""


PRINT_FORMAT_CSS = """
@page {
  margin: 14mm 12mm 16mm;
}

.print-format {
  padding: 0 !important;
}

.rt-print {
  color: #3f3a34;
  font-size: 11px;
  line-height: 1.45;
  orphans: 3;
  widows: 3;
}

.rt-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 22px;
  padding: 18px 4px 24px;
  border-bottom: 2px solid #e8dac4;
  break-inside: avoid;
  page-break-inside: avoid;
  break-after: avoid;
  page-break-after: avoid;
}

.rt-brand-block {
  max-width: 54%;
}

.rt-brand-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.rt-logo {
  display: block;
  max-width: 144px;
  max-height: 76px;
  object-fit: contain;
}

.rt-logo-fallback {
  width: 68px;
  height: 68px;
  border-radius: 50%;
  background: #f6f0e6;
  color: #9a7b53;
  font-size: 21px;
  font-weight: 700;
  line-height: 68px;
  text-align: center;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.rt-company-wrap {
  padding-top: 2px;
}

.rt-eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #9a7b53;
}

.rt-doc-name {
  margin: 8px 0 14px;
  font-size: 25px;
  font-weight: 800;
  line-height: 1.05;
  color: #1f2937;
}

.rt-company-name {
  font-size: 17px;
  font-weight: 700;
  color: #1f2937;
}

.rt-company-address {
  margin-top: 8px;
  font-size: 10px;
  color: #6b6258;
}

.rt-meta-card {
  min-width: 240px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid #e8dac4;
  background: #fcfaf6;
  break-inside: avoid;
  page-break-inside: avoid;
}

.rt-meta-row,
.rt-total-row,
.rt-grand-total {
  display: flex;
  justify-content: space-between;
  gap: 18px;
}

.rt-meta-row {
  padding: 7px 0;
  border-bottom: 1px solid #ede5d7;
  font-size: 10px;
}

.rt-meta-row:last-child {
  border-bottom: 0;
}

.rt-meta-row span {
  color: #8b8174;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.rt-meta-row strong {
  font-size: 11px;
  color: #1f2937;
}

.rt-party-grid,
.rt-summary-grid {
  display: flex;
  justify-content: space-between;
  gap: 20px;
}

.rt-party-grid {
  margin-top: 20px;
  break-inside: avoid;
  page-break-inside: avoid;
}

.rt-party-card,
.rt-summary-note-card,
.rt-totals-card,
.rt-notes {
  border-radius: 16px;
  border: 1px solid #eadfce;
  background: #fffdf9;
}

.rt-party-card {
  width: 50%;
  padding: 16px 18px;
  break-inside: avoid;
  page-break-inside: avoid;
}

.rt-section-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #9a7b53;
  break-after: avoid;
  page-break-after: avoid;
}

.rt-party-name {
  margin-top: 10px;
  font-size: 14px;
  font-weight: 800;
  color: #1f2937;
}

.rt-party-address,
.rt-party-ref,
.rt-party-extra,
.rt-terms,
.rt-in-words,
.rt-summary-note,
.rt-footer {
  margin-top: 8px;
  font-size: 10px;
  color: #6b6258;
}

.rt-party-extra {
  line-height: 1.5;
}

.rt-items {
  width: 100%;
  margin-top: 22px;
  border-collapse: separate;
  border-spacing: 0;
  border: 1px solid #eadfce;
  border-radius: 16px;
  overflow: hidden;
  page-break-inside: auto;
  break-inside: auto;
}

.rt-items thead {
  display: table-header-group;
}

.rt-items tbody {
  display: table-row-group;
}

.rt-items thead th {
  padding: 13px 14px;
  background: #f7f2ea;
  color: #6a5d4f;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  border-bottom: 1px solid #eadfce;
}

.rt-items tbody td {
  padding: 14px;
  vertical-align: top;
  border-bottom: 1px solid #f1e8da;
}

.rt-items tbody tr,
.rt-items tbody td {
  break-inside: avoid;
  page-break-inside: avoid;
}

.rt-items tbody tr:last-child td {
  border-bottom: 0;
}

.rt-col-idx {
  width: 40px;
}

.rt-col-qty {
  width: 100px;
}

.rt-col-rate,
.rt-col-amount {
  width: 130px;
  text-align: right;
}

.rt-idx {
  font-size: 10px;
  font-weight: 700;
  color: #9a7b53;
}

.rt-item-name {
  font-size: 11px;
  font-weight: 700;
  color: #1f2937;
  break-after: avoid;
  page-break-after: avoid;
}

.rt-item-description {
  margin-top: 5px;
  font-size: 10px;
  color: #6b6258;
}

.rt-num {
  text-align: right;
  font-size: 11px;
  color: #1f2937;
}

.rt-nowrap {
  white-space: nowrap;
}

.rt-summary-grid {
  margin-top: 20px;
  align-items: flex-start;
  break-inside: avoid;
  page-break-inside: avoid;
}

.rt-summary-note-card {
  width: 58%;
  padding: 16px 18px;
  background: #fffdf9;
  break-inside: avoid;
  page-break-inside: avoid;
}

.rt-summary-note {
  line-height: 1.45;
}

.rt-notes {
  margin-top: 18px;
  padding: 16px 18px 14px;
  page-break-inside: auto;
  break-inside: auto;
}

.rt-terms {
  column-count: 2;
  column-gap: 22px;
  column-rule: 1px solid #efe6d8;
}

.rt-terms .ql-editor,
.rt-terms div,
.rt-terms p {
  padding: 0 !important;
  margin: 0 0 4px !important;
  line-height: 1.35;
  orphans: 3;
  widows: 3;
}

.rt-terms p,
.rt-terms li {
  break-inside: avoid;
  page-break-inside: avoid;
}

.rt-terms strong {
  color: #4d463f;
  font-weight: 600;
}

.rt-in-words {
  margin-top: 10px;
  font-style: italic;
  color: #8b8174;
  line-height: 1.5;
}

.rt-totals-card {
  width: 38%;
  padding: 12px 16px 14px;
  background: #fcfaf6;
  break-inside: avoid;
  page-break-inside: avoid;
}

.rt-total-row {
  padding: 10px 0;
  border-bottom: 1px solid #ede5d7;
  font-size: 11px;
}

.rt-total-row span {
  color: #6b6258;
}

.rt-grand-total {
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid #d8c3a0;
  background: #f8f1e5;
  color: #1f2937;
  font-size: 13px;
  break-inside: avoid;
  page-break-inside: avoid;
}

.rt-footer {
  margin-top: 22px;
  padding-top: 12px;
  border-top: 1px solid #e8dac4;
  break-inside: avoid;
  page-break-inside: avoid;
}

.rt-footer-note {
  text-align: center;
  color: #5f574f;
}

.rt-footer-legal {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px 14px;
  margin-top: 10px;
  font-size: 9px;
  color: #8b8174;
}

@media print {
  .rt-header {
    padding-top: 0;
  }

  .rt-party-grid {
    display: table;
    width: 100%;
    table-layout: fixed;
    border-spacing: 20px 0;
    margin-left: -20px;
    margin-right: -20px;
  }

  .rt-party-card {
    display: table-cell;
    width: 50%;
  }

  .rt-items {
    overflow: visible;
  }

  .rt-items thead {
    display: table-header-group;
  }

  .rt-items tfoot {
    display: table-footer-group;
  }

  .rt-items tr,
  .rt-items td,
  .rt-items th {
    break-inside: avoid;
    page-break-inside: avoid;
  }

  .rt-summary-grid {
    display: table;
    width: 100%;
    table-layout: fixed;
    border-spacing: 20px 0;
    margin-left: -20px;
    margin-right: -20px;
  }

  .rt-summary-note-card,
  .rt-totals-card {
    display: table-cell;
    vertical-align: top;
  }

  .rt-summary-note-card {
    width: 56%;
  }

  .rt-notes {
    width: auto;
    margin-top: 16px;
  }

  .rt-terms {
    column-count: 2;
    column-gap: 18px;
    column-fill: balance;
  }

  .rt-terms,
  .rt-terms .ql-editor {
    break-inside: auto;
    page-break-inside: auto;
  }

  .rt-totals-card {
    width: 44%;
    min-width: 260px;
  }

  .rt-header,
  .rt-party-card,
  .rt-items,
  .rt-summary-grid,
  .rt-summary-note-card,
  .rt-totals-card,
  .rt-footer,
  .rt-meta-card,
  .rt-grand-total {
    break-inside: avoid;
    break-inside: avoid-page;
    page-break-inside: avoid;
  }

  .rt-section-title,
  .rt-item-name,
  .rt-footer-note {
    break-after: avoid;
    page-break-after: avoid;
  }
}
"""


def sync_print_formats() -> None:
    for config in PRINT_FORMATS:
        values = {
            "doctype": "Print Format",
            "name": config["name"],
            "print_format_for": "DocType",
            "doc_type": config["doc_type"],
            "module": config["module"],
            "standard": "No",
            "custom_format": 1,
            "disabled": 0,
            "print_format_type": "Jinja",
            "raw_printing": 0,
            "html": PRINT_FORMAT_HTML,
            "css": PRINT_FORMAT_CSS,
            "margin_top": 10,
            "margin_bottom": 10,
            "margin_left": 8,
            "margin_right": 8,
            "align_labels_right": 0,
            "show_section_headings": 0,
            "line_breaks": 0,
            "absolute_value": 0,
            "font_size": 11,
            "page_number": "Bottom Right",
            "print_format_builder": 0,
            "print_format_builder_beta": 0,
        }

        if frappe.db.exists("Print Format", config["name"]):
            print_format = frappe.get_doc("Print Format", config["name"])
            print_format.update(values)
            print_format.save(ignore_permissions=True)
        else:
            print_format = frappe.get_doc(values)
            print_format.insert(ignore_permissions=True)

    frappe.db.commit()
