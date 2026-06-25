# sandeep_reports

Custom **ERPNext / Frappe v16** reports built for the RBOL / Ethanol site, kept here for
version control and re-deployment. Each is a **DB-stored "Script Report"** (`is_standard = No`)
— the Python (`report_script`) and client script (`javascript`) live in the database, so this
repo stores them as plain files plus a small installer that (re)creates the `Report` documents
on any site.

## Reports

| Report | Based on | What it does |
|---|---|---|
| **Debtors Summary - Split** | GL Entry | Receivable summary, tree by Customer Group → Customer. The single *Invoiced* column is split into **Sales Invoice / Debit Note / Credit Note**. |
| **Creditors Summary - Split** | GL Entry | Payable summary, tree by Supplier Group → Supplier, *Invoiced* split into **Purchase Invoice / Credit Note / Debit Note**. |
| **Stock Summary** | Stock Ledger Entry | Tally-style Warehouse → Item Group → Item tree with Opening / Inward / Outward / Closing (Qty + Value). |
| **Daily Business Summary** | Sales Invoice | Day-wise business snapshot. |
| **Receivable Follow-up** | Sales Invoice | Lightweight collections list — pending bills, due dates, overdue days and customer mobile, grouped by Customer Group / Customer / Voucher. |

## Correctness notes

- **Debtors/Creditors Summary - Split** read directly from **`GL Entry` (`is_cancelled = 0`)** — the
  same source the *General Ledger* report drills into — so Outstanding always reconciles with the GL
  and cancelled/amended vouchers are handled correctly. Identity holds exactly:
  `Outstanding = Opening + Invoice + Debit Note − Credit Note − Received/Paid`.
- **Stock Summary**: Inward/Outward **Value** is keyed off `stock_value_difference` sign (not
  `actual_qty`), so zero-qty revaluations (Stock Reconciliation) are captured and
  `Closing Value = Opening + Inward − Outward` reconciles exactly. Closing matches the standard
  *Stock Balance* report. Filters (Warehouse, Item Group) are tree-inclusive.
- **Receivable Follow-up** is invoice-level (`Sales Invoice.outstanding_amount`), so it intentionally
  excludes on-account/unallocated credits and JE adjustments — it is a "which bills to chase" view,
  not a GL reconciliation.

Every report has a collapsible tree, drill-down links, INR summary cards and an **Export to Excel**
button.

## Install / update on a site

```bash
cd /path/to/sandeep_reports        # this repo
bench --site <your-site> console <<'EOF'
import os
os.environ["SANDEEP_REPORTS_DIR"] = "/home/jajula_sandeep/sandeep_reports"   # <- repo path
exec(open(os.path.join(os.environ["SANDEEP_REPORTS_DIR"], "install.py")).read())
EOF
```

The installer is idempotent — it creates each `Report` if missing or updates the script/JS/roles if
it already exists, then commits. Clear cache afterwards: `bench --site <your-site> clear-cache`.

> These are non-standard (DB) reports: `server_script_enabled` must be `1` in the site config for
> Script Reports to execute.
