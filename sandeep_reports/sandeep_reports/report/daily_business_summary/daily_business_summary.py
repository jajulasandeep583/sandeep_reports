# Daily Business Summary — standard Script Report (auto-converted from safe_exec DB script)
import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	from_date = filters.get("from_date") or frappe.utils.nowdate()
	to_date   = filters.get("to_date")   or frappe.utils.nowdate()
	company   = filters.get("company")   or frappe.db.get_default("Company")

	columns = [
	    {"fieldname": "section",  "label": "Section",  "fieldtype": "Data",     "width": 450},
	    {"fieldname": "count",    "label": "Count",    "fieldtype": "Int",      "width": 80},
	    {"fieldname": "amount",   "label": "Amount",   "fieldtype": "Currency", "width": 200},
	    {"fieldname": "row_type", "label": "Type",     "fieldtype": "Data",     "hidden": 1},
	]

	params = {"fd": from_date, "td": to_date, "co": company}

	# ── Sales Invoices — net of credit notes ──────────────────────
	# is_return=1 means credit note (negative grand_total already stored negative)
	# SUM(grand_total) nets them off automatically
	sales = frappe.db.sql("""
	    SELECT
	        SUM(CASE WHEN is_return = 0 THEN 1 ELSE 0 END) AS cnt,
	        IFNULL(SUM(CASE WHEN is_return = 0 THEN grand_total ELSE 0 END), 0) AS total,
	        IFNULL(SUM(base_net_total), 0) AS net_total
	    FROM `tabSales Invoice`
	    WHERE docstatus = 1
	    AND posting_date BETWEEN %(fd)s AND %(td)s
	    AND company = %(co)s
	""", params, as_dict=True)[0]

	# ── Purchase Invoices — net of debit notes ────────────────────
	purchases = frappe.db.sql("""
	    SELECT
	        SUM(CASE WHEN is_return = 0 THEN 1 ELSE 0 END) AS cnt,
	        IFNULL(SUM(CASE WHEN is_return = 0 THEN grand_total ELSE 0 END), 0) AS total,
	        IFNULL(SUM(base_net_total), 0) AS net_total
	    FROM `tabPurchase Invoice`
	    WHERE docstatus = 1
	    AND posting_date BETWEEN %(fd)s AND %(td)s
	    AND company = %(co)s
	""", params, as_dict=True)[0]

	# ── Collections — Payment Entry ────────────────────────────────
	collections = frappe.db.sql("""
	    SELECT COUNT(*) AS cnt, IFNULL(SUM(paid_amount), 0) AS total
	    FROM `tabPayment Entry`
	    WHERE docstatus = 1
	    AND payment_type = 'Receive'
	    AND posting_date BETWEEN %(fd)s AND %(td)s
	    AND company = %(co)s
	""", params, as_dict=True)[0]

	# ── Payments — Payment Entry ───────────────────────────────────
	payments = frappe.db.sql("""
	    SELECT COUNT(*) AS cnt, IFNULL(SUM(paid_amount), 0) AS total
	    FROM `tabPayment Entry`
	    WHERE docstatus = 1
	    AND payment_type = 'Pay'
	    AND posting_date BETWEEN %(fd)s AND %(td)s
	    AND company = %(co)s
	""", params, as_dict=True)[0]

	# ── Collections — Journal Entry ────────────────────────────────
	je_recv = frappe.db.sql("""
	    SELECT COUNT(DISTINCT gle.voucher_no) AS cnt,
	           IFNULL(SUM(gle.debit), 0) AS total
	    FROM `tabGL Entry` gle
	    INNER JOIN `tabAccount` acc ON acc.name = gle.account
	    INNER JOIN `tabJournal Entry` je ON je.name = gle.voucher_no
	    WHERE gle.voucher_type = 'Journal Entry'
	    AND je.voucher_type IN ('Bank Entry', 'Cash Entry')
	    AND acc.account_type IN ('Bank', 'Cash')
	    AND gle.debit > 0
	    AND gle.is_cancelled = 0
	    AND gle.posting_date BETWEEN %(fd)s AND %(td)s
	    AND gle.company = %(co)s
	""", params, as_dict=True)[0]

	# ── Payments — Journal Entry ───────────────────────────────────
	je_pay = frappe.db.sql("""
	    SELECT COUNT(DISTINCT gle.voucher_no) AS cnt,
	           IFNULL(SUM(gle.credit), 0) AS total
	    FROM `tabGL Entry` gle
	    INNER JOIN `tabAccount` acc ON acc.name = gle.account
	    INNER JOIN `tabJournal Entry` je ON je.name = gle.voucher_no
	    WHERE gle.voucher_type = 'Journal Entry'
	    AND je.voucher_type IN ('Bank Entry', 'Cash Entry')
	    AND acc.account_type IN ('Bank', 'Cash')
	    AND gle.credit > 0
	    AND gle.is_cancelled = 0
	    AND gle.posting_date BETWEEN %(fd)s AND %(td)s
	    AND gle.company = %(co)s
	""", params, as_dict=True)[0]

	# ── Purchase Orders pending ────────────────────────────────────
	pending_po = frappe.db.sql("""
	    SELECT COUNT(*) AS cnt, IFNULL(SUM(grand_total), 0) AS total
	    FROM `tabPurchase Order`
	    WHERE docstatus = 1
	    AND status NOT IN ('Completed','Cancelled','Closed')
	    AND company = %(co)s
	""", {"co": company}, as_dict=True)[0]

	# ── Sales Orders pending ───────────────────────────────────────
	pending_so = frappe.db.sql("""
	    SELECT COUNT(*) AS cnt, IFNULL(SUM(grand_total), 0) AS total
	    FROM `tabSales Order`
	    WHERE docstatus = 1
	    AND status NOT IN ('Completed','Cancelled','Closed')
	    AND company = %(co)s
	""", {"co": company}, as_dict=True)[0]

	# ── Total Outstanding Receivable — Payment Ledger Entry ───────
	receivable = frappe.db.sql("""
	    SELECT IFNULL(SUM(amount), 0) AS total
	    FROM `tabPayment Ledger Entry`
	    WHERE party_type = 'Customer'
	    AND delinked = 0
	    AND posting_date <= %(td)s
	    AND company = %(co)s
	""", {"td": to_date, "co": company}, as_dict=True)[0]

	# ── Total Outstanding Payable — Payment Ledger Entry ─────────
	payable = frappe.db.sql("""
	    SELECT IFNULL(SUM(amount), 0) AS total
	    FROM `tabPayment Ledger Entry`
	    WHERE party_type = 'Supplier'
	    AND delinked = 0
	    AND posting_date <= %(td)s
	    AND company = %(co)s
	""", {"td": to_date, "co": company}, as_dict=True)[0]

	# ── Totals ─────────────────────────────────────────────────────
	# Use base_net_total for sales/purchase to match Sales Invoice Trends
	# base_net_total = taxable value (excl GST), same as what trends report shows
	s   = frappe.utils.flt(sales.get("net_total"))
	p   = frappe.utils.flt(purchases.get("net_total"))
	c   = frappe.utils.flt(collections.get("total"))
	py_ = frappe.utils.flt(payments.get("total"))
	jc  = frappe.utils.flt(je_recv.get("total"))
	jp  = frappe.utils.flt(je_pay.get("total"))
	net = (c + jc) - (py_ + jp)

	receivable_amt = frappe.utils.flt(receivable.get("total"))
	payable_amt    = abs(frappe.utils.flt(payable.get("total")))

	rows = [
	    # ── SALES ──────────────────────────────────────────────────
	    {"section": "─── SALES",            "count": None, "amount": None,           "row_type": "header"},
	    {"section": "Sales Invoices",        "count": frappe.utils.cint(sales.get("cnt")),      "amount": s,              "row_type": "sales"},
	    {"section": "Sales Orders Pending",  "count": frappe.utils.cint(pending_so.get("cnt")), "amount": frappe.utils.flt(pending_so.get("total")), "row_type": "info_so"},
	    {"section": "Total Receivable",      "count": None,                                      "amount": receivable_amt, "row_type": "total_recv"},

	    # ── PURCHASES ──────────────────────────────────────────────
	    {"section": "─── PURCHASES",          "count": None, "amount": None,         "row_type": "header"},
	    {"section": "Purchase Invoices",       "count": frappe.utils.cint(purchases.get("cnt")), "amount": p,            "row_type": "purchase"},
	    {"section": "Purchase Orders Pending", "count": frappe.utils.cint(pending_po.get("cnt")), "amount": frappe.utils.flt(pending_po.get("total")), "row_type": "info_po"},
	    {"section": "Total Payable",           "count": None,                                      "amount": payable_amt, "row_type": "total_pay"},

	    # ── CASH FLOW ───────────────────────────────────────────────
	    {"section": "─── CASH FLOW",         "count": None, "amount": None, "row_type": "header"},
	    {"section": "Collections (PE)",       "count": frappe.utils.cint(collections.get("cnt")), "amount": c,   "row_type": "collection"},
	    {"section": "Collections (JE)",       "count": frappe.utils.cint(je_recv.get("cnt")),      "amount": jc,  "row_type": "je_collection"},
	    {"section": "Payments (PE)",          "count": frappe.utils.cint(payments.get("cnt")),     "amount": py_, "row_type": "payment"},
	    {"section": "Payments (JE)",          "count": frappe.utils.cint(je_pay.get("cnt")),       "amount": jp,  "row_type": "je_payment"},
	    {"section": "Net Cash Flow",          "count": None,                                        "amount": net, "row_type": "net"},
	]

	report_summary = [
	    {"value": s,        "label": "Sales",       "datatype": "Currency", "currency": "INR", "indicator": "green"},
	    {"value": p,        "label": "Purchases",   "datatype": "Currency", "currency": "INR", "indicator": "red"},
	    {"value": c + jc,   "label": "Collections", "datatype": "Currency", "currency": "INR", "indicator": "green"},
	    {"value": py_ + jp, "label": "Payments",    "datatype": "Currency", "currency": "INR", "indicator": "red"},
	    {"value": net,      "label": "Net Cash",    "datatype": "Currency", "currency": "INR", "indicator": "blue"},
	]

	data = columns, rows, None, None, report_summary
	return data
