app_name        = "sandeep_reports"
app_title       = "Sandeep Reports"
app_publisher   = "Sandeep"
app_description = "Custom ERPNext v16 reports: Debtors/Creditors Summary Split, Stock Summary, Daily Business Summary, Receivable Follow-up, Store Shift Report"
app_email       = "jajulasandeep583@gmail.com"
app_license     = "MIT"
app_version     = "1.0.0"

source_link = "https://github.com/jajulasandeep583/sandeep_reports"

# These reports query Frappe + ERPNext doctypes (GL Entry, Sales Invoice,
# Stock Ledger Entry, ...) so ERPNext is required.
required_apps = ["frappe", "erpnext"]

# The reports are shipped as standard Script Reports under
# sandeep_reports/sandeep_reports/report/. Frappe imports/updates them
# automatically on `bench install-app` and every `bench migrate` -- no
# custom installer needed.
