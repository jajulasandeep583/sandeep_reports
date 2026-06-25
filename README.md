# Sandeep Reports

A **Frappe / ERPNext v16** app that bundles five custom reports for the RBOL / Ethanol
ERP. Each is a **Script Report** kept in the database; the app ships them as files and
recreates them automatically on install and on every `bench migrate`.

> Requires **Frappe v16** and **ERPNext v16** (the reports query ERPNext doctypes).
> `server_script_enabled` must be `1` in the site config for Script Reports to run.

## Reports

| Report | Module | Based on | What it does |
|---|---|---|---|
| **Debtors Summary - Split** | Accounts | GL Entry | Receivable summary (Customer Group → Customer tree). *Invoiced* split into **Sales Invoice / Debit Note / Credit Note**. |
| **Creditors Summary - Split** | Accounts | GL Entry | Payable summary (Supplier Group → Supplier). *Invoiced* split into **Purchase Invoice / Credit Note / Debit Note**. |
| **Stock Summary** | Stock | Stock Ledger Entry | Tally-style Warehouse → Item Group → Item with Opening / Inward / Outward / Closing (Qty + Value). |
| **Daily Business Summary** | Accounts | Sales Invoice | Day-wise business snapshot. |
| **Receivable Follow-up** | Accounts | Sales Invoice | Lightweight collections list — pending bills, due dates, overdue days, customer mobile; group by Customer Group / Customer / Voucher. |

All have a collapsible tree, drill-down links, INR summary cards and an **Export to Excel** button.

## Correctness

- **Debtors / Creditors Summary - Split** read directly from **`GL Entry` (`is_cancelled = 0`)** — the
  same source the *General Ledger* report drills into — so Outstanding always reconciles with the GL
  and cancelled/amended vouchers are handled correctly:
  `Outstanding = Opening + Invoice + Debit Note − Credit Note − Received/Paid` (exact).
- **Stock Summary**: Inward/Outward **Value** is keyed off `stock_value_difference` (not `actual_qty`),
  so zero-qty revaluations are captured and `Closing Value = Opening + Inward − Outward` reconciles
  exactly; closing matches the standard *Stock Balance* report. Warehouse & Item Group filters are
  tree-inclusive.
- **Receivable Follow-up** is invoice-level (`Sales Invoice.outstanding_amount`) — a "which bills to
  chase" view; it intentionally excludes on-account credits / JE adjustments and is not a GL recon.

## Install

```bash
# on a Frappe v16 bench
bench get-app https://github.com/jajulasandeep583/sandeep_reports.git
bench --site <your-site> install-app sandeep_reports
bench --site <your-site> clear-cache
```

To update after pulling new commits:

```bash
bench --site <your-site> migrate    # after_migrate re-applies the reports
```

## Layout

```
sandeep_reports/
  pyproject.toml
  sandeep_reports/
    hooks.py            # required_apps + after_install/after_migrate
    install.py          # idempotent report installer
    modules.txt         # "Sandeep Reports"
    reports_data/       # the report sources + manifest.json
      <slug>/<slug>.py  # report_script
      <slug>/<slug>.js  # client script
      <slug>/<slug>.json# report meta (type, ref doctype, module, roles)
```
