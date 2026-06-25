app_name        = "sandeep_reports"
app_title       = "Sandeep Reports"
app_publisher   = "Sandeep"
app_description = "Custom ERPNext v16 reports: Debtors/Creditors Summary Split, Stock Summary, Daily Business Summary, Receivable Follow-up"
app_email       = "jajulasandeep583@gmail.com"
app_license     = "MIT"
app_version     = "1.0.0"

source_link = "https://github.com/jajulasandeep583/sandeep_reports"

# These reports query Frappe + ERPNext doctypes (GL Entry, Sales Invoice,
# Stock Ledger Entry, …) so ERPNext is required.
required_apps = ["frappe", "erpnext"]

# The reports are stored in the database as non-standard Script Reports. The
# installer (re)creates them after the app is installed and after every migrate,
# so a fresh `bench install-app sandeep_reports` is enough — no manual import.
after_install = "sandeep_reports.install.install_reports"
after_migrate = "sandeep_reports.install.install_reports"
