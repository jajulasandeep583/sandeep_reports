# Creditors Summary - Split — standard Script Report (auto-converted from safe_exec DB script)
import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	as_on_date = filters.get("as_on_date") or frappe.utils.nowdate()
	company    = filters.get("company")    or frappe.db.get_default("Company")

	if filters.get("from_date"):
	    from_date = filters.get("from_date")
	else:
	    fy_start = frappe.db.get_value("Fiscal Year",
	        {"year_start_date": ("<=", as_on_date), "year_end_date": (">=", as_on_date)},
	        "year_start_date")
	    from_date = str(fy_start) if fy_start else as_on_date

	columns = [
	    {"fieldname": "row_id",           "label": "Row ID",           "fieldtype": "Data",     "hidden": 1},
	    {"fieldname": "parent_id",        "label": "Parent ID",        "fieldtype": "Data",     "hidden": 1},
	    {"fieldname": "party_id",         "label": "Party ID",         "fieldtype": "Data",     "hidden": 1},
	    {"fieldname": "label",            "label": "Supplier",         "fieldtype": "Data",     "width": 380},
	    {"fieldname": "opening",          "label": "Opening",          "fieldtype": "Currency", "width": 150},
	    {"fieldname": "purchase_invoice", "label": "Purchase Invoice", "fieldtype": "Currency", "width": 160},
	    {"fieldname": "credit_note",      "label": "Credit Note",      "fieldtype": "Currency", "width": 150},
	    {"fieldname": "debit_note",       "label": "Debit Note",       "fieldtype": "Currency", "width": 150},
	    {"fieldname": "paid",             "label": "Paid",             "fieldtype": "Currency", "width": 150},
	    {"fieldname": "outstanding",      "label": "Outstanding",      "fieldtype": "Currency", "width": 160},
	]

	MEASURES = ["opening", "purchase_invoice", "credit_note", "debit_note", "paid", "outstanding"]

	# ── 1. Party financial data ───────────────────────────────────────────────────
	# Reads directly from `GL Entry` (is_cancelled = 0) so totals always match the
	# General Ledger drill-down, and cancelled/amended vouchers are handled exactly
	# like GL. For a supplier the payable increases on CREDIT, so per-row movement
	# = credit - debit. The period movement is split by voucher type:
	#   purchase_invoice = Purchase Invoice rows that INCREASE payable (is_return=0)
	#   credit_note      = Journal Entry increases to payable (non-bill increases)
	#   debit_note       = all non-payment REDUCTIONS -> Purchase returns (is_return=1) + JV reductions
	#   paid             = Payment Entry only (net; a refund reduces this)
	#   opening          = net (credit - debit) of all non-cancelled entries before from_date
	#   outstanding      = net of all non-cancelled entries up to as_on_date
	#   Identity: outstanding = opening + purchase_invoice + credit_note - debit_note - paid
	#   (exact, because only Purchase Invoice / Journal Entry / Payment Entry hit the
	#    party account, and every row lands in exactly one bucket)
	party_data = frappe.db.sql("""
	    SELECT
	        s.supplier_group  AS grp,
	        gle.party         AS party,
	        s.supplier_name   AS party_name,
	        SUM(CASE WHEN gle.posting_date < %(fd)s
	            THEN gle.credit - gle.debit ELSE 0 END)                            AS opening,
	        SUM(CASE WHEN gle.voucher_type = 'Purchase Invoice' AND (gle.credit - gle.debit) > 0
	                 AND gle.posting_date >= %(fd)s AND gle.posting_date <= %(d)s
	            THEN gle.credit - gle.debit ELSE 0 END)                            AS purchase_invoice,
	        SUM(CASE WHEN gle.voucher_type = 'Journal Entry' AND (gle.credit - gle.debit) > 0
	                 AND gle.posting_date >= %(fd)s AND gle.posting_date <= %(d)s
	            THEN gle.credit - gle.debit ELSE 0 END)                            AS credit_note,
	        ABS(SUM(CASE WHEN (gle.credit - gle.debit) < 0
	                     AND gle.voucher_type IN ('Purchase Invoice', 'Journal Entry')
	                     AND gle.posting_date >= %(fd)s AND gle.posting_date <= %(d)s
	            THEN gle.credit - gle.debit ELSE 0 END))                           AS debit_note,
	        -SUM(CASE WHEN gle.voucher_type = 'Payment Entry'
	                  AND gle.posting_date >= %(fd)s AND gle.posting_date <= %(d)s
	            THEN gle.credit - gle.debit ELSE 0 END)                            AS paid,
	        SUM(gle.credit - gle.debit)                                            AS outstanding
	    FROM `tabGL Entry` gle
	    INNER JOIN `tabSupplier` s ON s.name = gle.party
	    WHERE
	        gle.party_type    = 'Supplier'
	        AND gle.is_cancelled = 0
	        AND gle.posting_date <= %(d)s
	        AND gle.company    = %(co)s
	    GROUP BY s.supplier_group, gle.party, s.supplier_name
	    HAVING ABS(SUM(gle.credit - gle.debit)) > 0.01
	    ORDER BY s.supplier_group, SUM(gle.credit - gle.debit) DESC
	""", {"fd": from_date, "d": as_on_date, "co": company}, as_dict=True)

	# ── 2. Supplier Group tree — lft order = parents always before children ───────
	cg_list = frappe.db.sql("""
	    SELECT name, parent_supplier_group
	    FROM `tabSupplier Group`
	    ORDER BY lft
	""", as_dict=True)

	cg_parent   = {}
	cg_children = {}
	for cg in cg_list:
	    cg_parent[cg["name"]] = cg.get("parent_supplier_group") or ""
	    p = cg.get("parent_supplier_group") or ""
	    if p:
	        cg_children.setdefault(p, []).append(cg["name"])

	# ── 3. Suppliers indexed by their direct group ────────────────────────────────
	customers_by_group = {}
	for r in party_data:
	    g = r.get("grp") or "Ungrouped"
	    customers_by_group.setdefault(g, []).append(r)

	# ── 4. Depth map ──────────────────────────────────────────────────────────────
	group_depth = {}
	group_depth["All Supplier Groups"] = -1
	for cg in cg_list:
	    gn = cg["name"]
	    if gn == "All Supplier Groups":
	        continue
	    p  = cg.get("parent_supplier_group") or ""
	    pd = group_depth.get(p, -1)
	    group_depth[gn] = pd + 1

	# ── 5. Aggregate & has_data — bottom-up via reverse index ─────────────────────
	group_agg      = {}
	group_has_data = {}

	for idx in range(len(cg_list) - 1, -1, -1):
	    cg = cg_list[idx]
	    gn = cg["name"]
	    agg = {m: 0.0 for m in MEASURES}
	    hd  = False
	    for c in customers_by_group.get(gn, []):
	        for m in MEASURES:
	            agg[m] = agg[m] + frappe.utils.flt(c.get(m))
	        hd = True
	    for child in cg_children.get(gn, []):
	        ca = group_agg.get(child) or {m: 0.0 for m in MEASURES}
	        for m in MEASURES:
	            agg[m] = agg[m] + ca[m]
	        if group_has_data.get(child):
	            hd = True
	    group_agg[gn]      = agg
	    group_has_data[gn] = hd

	# ── 6. Build rows ─────────────────────────────────────────────────────────────
	rows          = []
	gid_counter   = [0]
	group_row_ids = {}

	for cg in cg_list:
	    gn = cg["name"]
	    if gn == "All Supplier Groups":
	        continue
	    if not group_has_data.get(gn):
	        continue
	    depth         = group_depth.get(gn, 0)
	    parent_cg     = cg.get("parent_supplier_group") or ""
	    parent_row_id = None
	    if parent_cg and parent_cg != "All Supplier Groups":
	        parent_row_id = group_row_ids.get(parent_cg)
	    gid_counter[0]    = gid_counter[0] + 1
	    g_row_id          = "G" + str(gid_counter[0])
	    group_row_ids[gn] = g_row_id
	    agg = group_agg.get(gn) or {m: 0.0 for m in MEASURES}
	    grow = {"row_id": g_row_id, "parent_id": parent_row_id, "party_id": None,
	            "label": gn, "indent": depth}
	    for m in MEASURES:
	        grow[m] = agg[m]
	    rows.append(grow)
	    for p in customers_by_group.get(gn, []):
	        gid_counter[0] = gid_counter[0] + 1
	        prow = {"row_id": "P" + str(gid_counter[0]), "parent_id": g_row_id,
	                "party_id": p.get("party") or "",
	                "label": p.get("party_name") or p.get("party") or "",
	                "indent": depth + 1}
	        for m in MEASURES:
	            prow[m] = frappe.utils.flt(p.get(m))
	        rows.append(prow)

	# ── 7. Fallback for groups not in ERPNext tree ────────────────────────────────
	known_groups = set(cg_parent.keys())
	for grp in sorted(customers_by_group.keys()):
	    if grp in known_groups:
	        continue
	    gid_counter[0] = gid_counter[0] + 1
	    g_row_id = "G" + str(gid_counter[0])
	    agg = {m: 0.0 for m in MEASURES}
	    for c in customers_by_group.get(grp, []):
	        for m in MEASURES:
	            agg[m] = agg[m] + frappe.utils.flt(c.get(m))
	    grow = {"row_id": g_row_id, "parent_id": None, "party_id": None,
	            "label": grp, "indent": 0}
	    for m in MEASURES:
	        grow[m] = agg[m]
	    rows.append(grow)
	    for p in customers_by_group.get(grp, []):
	        gid_counter[0] = gid_counter[0] + 1
	        prow = {"row_id": "P" + str(gid_counter[0]), "parent_id": g_row_id,
	                "party_id": p.get("party") or "",
	                "label": p.get("party_name") or p.get("party") or "",
	                "indent": 1}
	        for m in MEASURES:
	            prow[m] = frappe.utils.flt(p.get(m))
	        rows.append(prow)

	# ── 8. Grand totals ───────────────────────────────────────────────────────────
	grand = {m: 0.0 for m in MEASURES}
	for r in party_data:
	    for m in MEASURES:
	        grand[m] = grand[m] + frappe.utils.flt(r.get(m))

	report_summary = [
	    {"value": grand["opening"],          "label": "Opening Balance", "datatype": "Currency", "currency": "INR", "indicator": "grey"},
	    {"value": grand["purchase_invoice"], "label": "Purchase Invoice","datatype": "Currency", "currency": "INR", "indicator": "orange"},
	    {"value": grand["credit_note"],      "label": "Credit Note",     "datatype": "Currency", "currency": "INR", "indicator": "purple"},
	    {"value": grand["debit_note"],       "label": "Debit Note",      "datatype": "Currency", "currency": "INR", "indicator": "blue"},
	    {"value": grand["paid"],             "label": "Paid",            "datatype": "Currency", "currency": "INR", "indicator": "green"},
	    {"value": grand["outstanding"],      "label": "Net Payable",     "datatype": "Currency", "currency": "INR", "indicator": "red"},
	]

	data = columns, rows, None, None, report_summary
	return data
