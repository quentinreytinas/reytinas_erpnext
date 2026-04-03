app_name = "reytinas_erpnext"
app_title = "Reytinas ERPNext"
app_publisher = "Quentin Reytinas"
app_description = "Custom ERPNext extensions for Reytinas"
app_email = "admin@reytinas.fr"
app_license = "MIT"
app_version = "0.2.0"

required_apps = ["erpnext"]

after_install = "reytinas_erpnext.print_formats.sync_print_formats"
after_migrate = "reytinas_erpnext.print_formats.sync_print_formats"
