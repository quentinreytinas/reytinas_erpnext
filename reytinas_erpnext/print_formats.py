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
{% set reference_label = "Devis" if is_quote else "Facture" %}
{% set customer_label = "Client" %}

<section class="rt-print">
  <header class="rt-header">
    <div class="rt-brand-block">
      <div class="rt-eyebrow">{{ title }}</div>
      <h1 class="rt-doc-name">{{ doc.name }}</h1>
      <div class="rt-company-name">{{ doc.company }}</div>
      {% if doc.company_address_display %}
        <div class="rt-company-address">{{ doc.company_address_display }}</div>
      {% endif %}
    </div>

    <div class="rt-meta-card">
      <div class="rt-meta-row">
        <span>{{ reference_label }}</span>
        <strong>{{ doc.name }}</strong>
      </div>
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
      <div class="rt-party-name">{{ doc.company }}</div>
      {% if doc.company_address_display %}
        <div class="rt-party-address">{{ doc.company_address_display }}</div>
      {% endif %}
    </div>

    <div class="rt-party-card">
      <div class="rt-section-title">{{ customer_label }}</div>
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

  <section class="rt-bottom-grid">
    <div class="rt-notes">
      {% if doc.terms %}
        <div class="rt-section-title">Conditions</div>
        <div class="rt-terms">{{ doc.terms }}</div>
      {% endif %}
      {% if doc.in_words %}
        <div class="rt-in-words">{{ doc.in_words }}</div>
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

  <footer class="rt-footer">
    {% if is_quote %}
      <span>Merci pour votre confiance. Ce devis reste valable jusqu'à la date indiquée ci-dessus.</span>
    {% else %}
      <span>Merci pour votre confiance. Merci de rappeler le numéro de facture lors de votre règlement.</span>
    {% endif %}
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
  color: #0f172a;
  font-size: 11px;
  line-height: 1.45;
}

.rt-header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 24px 24px 22px;
  border-radius: 18px;
  background: #0f172a;
  color: #f8fafc;
}

.rt-brand-block {
  max-width: 58%;
}

.rt-eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #fbbf24;
}

.rt-doc-name {
  margin: 10px 0 18px;
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
  color: #ffffff;
}

.rt-company-name {
  font-size: 14px;
  font-weight: 700;
}

.rt-company-address {
  margin-top: 8px;
  font-size: 10px;
  color: #cbd5e1;
}

.rt-meta-card {
  min-width: 220px;
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.08);
}

.rt-meta-row,
.rt-total-row,
.rt-grand-total {
  display: flex;
  justify-content: space-between;
  gap: 18px;
}

.rt-meta-row {
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 10px;
}

.rt-meta-row:last-child {
  border-bottom: 0;
}

.rt-meta-row span {
  color: #cbd5e1;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.rt-meta-row strong {
  font-size: 11px;
  color: #ffffff;
}

.rt-party-grid,
.rt-bottom-grid {
  display: flex;
  justify-content: space-between;
  gap: 20px;
}

.rt-party-grid {
  margin-top: 20px;
}

.rt-party-card,
.rt-totals-card,
.rt-notes {
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.rt-party-card {
  width: 50%;
  padding: 16px 18px;
}

.rt-section-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #64748b;
}

.rt-party-name {
  margin-top: 10px;
  font-size: 14px;
  font-weight: 800;
  color: #0f172a;
}

.rt-party-address,
.rt-party-ref,
.rt-terms,
.rt-in-words,
.rt-footer {
  margin-top: 8px;
  font-size: 10px;
  color: #475569;
}

.rt-items {
  width: 100%;
  margin-top: 22px;
  border-collapse: separate;
  border-spacing: 0;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  overflow: hidden;
}

.rt-items thead th {
  padding: 13px 14px;
  background: #f8fafc;
  color: #334155;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  border-bottom: 1px solid #e2e8f0;
}

.rt-items tbody td {
  padding: 14px;
  vertical-align: top;
  border-bottom: 1px solid #e2e8f0;
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
  color: #64748b;
}

.rt-item-name {
  font-size: 11px;
  font-weight: 700;
  color: #0f172a;
}

.rt-item-description {
  margin-top: 5px;
  font-size: 10px;
  color: #475569;
}

.rt-num {
  text-align: right;
  font-size: 11px;
  color: #0f172a;
}

.rt-nowrap {
  white-space: nowrap;
}

.rt-bottom-grid {
  margin-top: 20px;
  align-items: flex-start;
}

.rt-notes {
  width: 58%;
  padding: 16px 18px;
}

.rt-in-words {
  margin-top: 14px;
  font-style: italic;
}

.rt-totals-card {
  width: 38%;
  padding: 10px 16px 14px;
}

.rt-total-row {
  padding: 10px 0;
  border-bottom: 1px solid #e2e8f0;
  font-size: 11px;
}

.rt-total-row span {
  color: #475569;
}

.rt-grand-total {
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: #0f172a;
  color: #ffffff;
  font-size: 13px;
}

.rt-footer {
  margin-top: 24px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
  text-align: center;
}

@media print {
  .rt-header,
  .rt-party-card,
  .rt-items,
  .rt-totals-card,
  .rt-notes {
    break-inside: avoid;
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
