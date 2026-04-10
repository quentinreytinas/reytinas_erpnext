app_name = "reytinas_erpnext"
app_title = "Reytinas ERPNext"
app_publisher = "Quentin Reytinas"
app_description = "Custom ERPNext extensions for Reytinas"
app_email = "admin@reytinas.fr"
app_license = "MIT"
app_version = "0.4.0"

required_apps = ["erpnext"]

doctype_js = {
    "EnableBanking Settings": "public/js/enablebanking_settings.js",
}

after_install = [
    "reytinas_erpnext.print_formats.sync_print_formats",
    "reytinas_erpnext.naming.sync_naming_series_property_setters",
]

after_migrate = [
    "reytinas_erpnext.print_formats.sync_print_formats",
    "reytinas_erpnext.naming.sync_naming_series_property_setters",
]

scheduler_events = {
    "hourly": [
        "reytinas_erpnext.enablebanking.sync.sync_all_links",
    ],
    "daily": [
        "reytinas_erpnext.enablebanking.sync.disable_expired_links",
    ],
}

doc_events = {
    "Quotation": {
        "autoname": "reytinas_erpnext.naming.set_quotation_name",
        "validate": "reytinas_erpnext.terms.sync_dynamic_terms",
    },
    "Sales Invoice": {
        "autoname": "reytinas_erpnext.naming.set_sales_invoice_name",
        "validate": "reytinas_erpnext.terms.sync_dynamic_terms",
    }
}
