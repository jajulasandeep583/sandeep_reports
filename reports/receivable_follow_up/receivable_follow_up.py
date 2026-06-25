# Receivable Follow-up — lightweight collections report (DB-stored Script Report)
# Source: open Sales Invoices (docstatus=1, outstanding_amount > 0). Shows which
# bills are pending, their due dates, days overdue and the customer's mobile so
# you can chase payment. Group By: Customer Group / Customer / Voucher.
today = frappe.utils.nowdate()
company = filters.get("company") or frappe.db.get_default("Company")
group_by = filters.get("group_by") or "Customer Group"

# ---- filter conditions ----
cond = ""
params = {"co": company}
if filters.get("posting_from_date"):
	cond = cond + " AND si.posting_date >= %(pfd)s"
	params["pfd"] = filters.get("posting_from_date")
if filters.get("posting_to_date"):
	cond = cond + " AND si.posting_date <= %(ptd)s"
	params["ptd"] = filters.get("posting_to_date")
if filters.get("due_from_date"):
	cond = cond + " AND si.due_date >= %(dfd)s"
	params["dfd"] = filters.get("due_from_date")
if filters.get("due_to_date"):
	cond = cond + " AND si.due_date <= %(dtd)s"
	params["dtd"] = filters.get("due_to_date")
if filters.get("customer"):
	cond = cond + " AND si.customer = %(cust)s"
	params["cust"] = filters.get("customer")
if filters.get("customer_group"):
	glr = frappe.db.get_value("Customer Group", filters.get("customer_group"), ["lft", "rgt"])
	if glr and glr[0] is not None:
		cond = cond + " AND c.customer_group IN (SELECT g2.name FROM `tabCustomer Group` g2 WHERE g2.lft >= %(cgl)s AND g2.rgt <= %(cgr)s)"
		params["cgl"] = glr[0]
		params["cgr"] = glr[1]
	else:
		cond = cond + " AND c.customer_group = %(cg)s"
		params["cg"] = filters.get("customer_group")
if filters.get("only_overdue"):
	cond = cond + " AND si.due_date < %(today)s"
	params["today"] = today

inv_rows = frappe.db.sql(
	"SELECT si.name AS invoice, si.customer AS party, c.customer_name AS party_name, "
	"c.customer_group AS grp, c.mobile_no AS mobile, "
	"si.posting_date AS posting_date, si.due_date AS due_date, "
	"si.grand_total AS invoiced, "
	"(si.grand_total - si.outstanding_amount) AS received, "
	"si.outstanding_amount AS outstanding "
	"FROM `tabSales Invoice` si "
	"INNER JOIN `tabCustomer` c ON c.name = si.customer "
	"WHERE si.docstatus = 1 AND si.outstanding_amount > 0.01 AND si.company = %(co)s" + cond + " "
	"ORDER BY si.due_date, si.posting_date, si.name",
	params, as_dict=True)

# overdue days per invoice
for r in inv_rows:
	od = 0
	if r.get("due_date"):
		dd = frappe.utils.date_diff(today, r.get("due_date"))
		if dd > 0:
			od = dd
	r["overdue_days"] = od

MET = ["invoiced", "received", "outstanding"]

columns = [
	{"fieldname": "row_id", "label": "Row ID", "fieldtype": "Data", "hidden": 1},
	{"fieldname": "parent_id", "label": "Parent ID", "fieldtype": "Data", "hidden": 1},
	{"fieldname": "node_type", "label": "Type", "fieldtype": "Data", "hidden": 1},
	{"fieldname": "invoice", "label": "Invoice", "fieldtype": "Data", "hidden": 1},
	{"fieldname": "label", "label": "Particulars", "fieldtype": "Data", "width": 330},
	{"fieldname": "mobile", "label": "Mobile", "fieldtype": "Data", "width": 130},
	{"fieldname": "posting_date", "label": "Posting Date", "fieldtype": "Date", "width": 110},
	{"fieldname": "due_date", "label": "Due Date", "fieldtype": "Date", "width": 110},
	{"fieldname": "overdue_days", "label": "Overdue Days", "fieldtype": "Int", "width": 110},
	{"fieldname": "bills", "label": "# Bills", "fieldtype": "Int", "width": 80},
	{"fieldname": "invoiced", "label": "Invoice Amt", "fieldtype": "Currency", "width": 140},
	{"fieldname": "received", "label": "Received", "fieldtype": "Currency", "width": 130},
	{"fieldname": "outstanding", "label": "Outstanding", "fieldtype": "Currency", "width": 150},
]

rows = []
counter = 0

# ---- per-customer aggregation ----
cust_invs = {}
cust_info = {}
for r in inv_rows:
	p = r.get("party")
	cust_invs.setdefault(p, []).append(r)
	if p not in cust_info:
		cust_info[p] = {"party_name": r.get("party_name") or p, "grp": r.get("grp") or "Ungrouped",
			"mobile": r.get("mobile") or ""}

cust_agg = {}
for p in cust_invs:
	a = {"invoiced": 0.0, "received": 0.0, "outstanding": 0.0, "bills": 0}
	for r in cust_invs[p]:
		for k in MET:
			a[k] = a[k] + frappe.utils.flt(r.get(k))
		a["bills"] = a["bills"] + 1
	cust_agg[p] = a


# NOTE: invoice-row emission is inlined in every branch on purpose — under
# safe_exec a helper function cannot see module-level vars (rows/counter).

if group_by == "Voucher":
	# flat list of pending invoices, most overdue first
	flat = sorted(inv_rows, key=lambda x: (-(x.get("overdue_days") or 0), x.get("due_date") or ""))
	for r in flat:
		counter = counter + 1
		rows.append({
			"row_id": "I" + str(counter), "parent_id": None, "node_type": "item",
			"invoice": r.get("invoice"),
			"label": (r.get("party_name") or r.get("party")) + " — " + r.get("invoice"),
			"mobile": r.get("mobile") or cust_info.get(r.get("party"), {}).get("mobile", ""),
			"posting_date": r.get("posting_date"), "due_date": r.get("due_date"),
			"overdue_days": r.get("overdue_days"), "bills": 1,
			"invoiced": frappe.utils.flt(r.get("invoiced")),
			"received": frappe.utils.flt(r.get("received")),
			"outstanding": frappe.utils.flt(r.get("outstanding")),
			"indent": 0,
		})

elif group_by == "Customer":
	pairs = []
	for p in cust_invs.keys():
		pairs.append((cust_agg[p]["outstanding"], p))
	pairs.sort(reverse=True)
	order = []
	for pr in pairs:
		order.append(pr[1])
	for p in order:
		counter = counter + 1
		crid = "C" + str(counter)
		info = cust_info[p]
		a = cust_agg[p]
		rows.append({
			"row_id": crid, "parent_id": None, "node_type": "customer", "invoice": None,
			"label": info["party_name"], "mobile": info["mobile"],
			"posting_date": None, "due_date": None, "overdue_days": None, "bills": a["bills"],
			"invoiced": a["invoiced"], "received": a["received"], "outstanding": a["outstanding"],
			"indent": 0,
		})
		for r in cust_invs[p]:
			counter = counter + 1
			rows.append({
				"row_id": "I" + str(counter), "parent_id": crid, "node_type": "item",
				"invoice": r.get("invoice"), "label": r.get("invoice"), "mobile": "",
				"posting_date": r.get("posting_date"), "due_date": r.get("due_date"),
				"overdue_days": r.get("overdue_days"), "bills": None,
				"invoiced": frappe.utils.flt(r.get("invoiced")),
				"received": frappe.utils.flt(r.get("received")),
				"outstanding": frappe.utils.flt(r.get("outstanding")),
				"indent": 1,
			})

else:
	# Customer Group tree -> Customer -> Invoice
	cg_rows = frappe.db.sql("SELECT name, parent_customer_group FROM `tabCustomer Group` ORDER BY lft", as_dict=True)
	cg_parent = {}
	cg_children = {}
	for g in cg_rows:
		cg_parent[g["name"]] = g.get("parent_customer_group") or ""
		pp = g.get("parent_customer_group") or ""
		if pp:
			cg_children.setdefault(pp, []).append(g["name"])

	custs_by_group = {}
	for p in cust_invs:
		custs_by_group.setdefault(cust_info[p]["grp"], []).append(p)

	# bottom-up group aggregation
	g_agg = {}
	g_has = {}
	for idx in range(len(cg_rows) - 1, -1, -1):
		gn = cg_rows[idx]["name"]
		a = {"invoiced": 0.0, "received": 0.0, "outstanding": 0.0, "bills": 0}
		hd = False
		for p in custs_by_group.get(gn, []):
			ca = cust_agg[p]
			for k in MET:
				a[k] = a[k] + ca[k]
			a["bills"] = a["bills"] + ca["bills"]
			hd = True
		for ch in cg_children.get(gn, []):
			if g_has.get(ch):
				cca = g_agg[ch]
				for k in MET:
					a[k] = a[k] + cca[k]
				a["bills"] = a["bills"] + cca["bills"]
				hd = True
		g_agg[gn] = a
		g_has[gn] = hd

	group_depth = {}
	group_depth["All Customer Groups"] = -1
	for g in cg_rows:
		gn = g["name"]
		if gn == "All Customer Groups":
			continue
		pp = g.get("parent_customer_group") or ""
		group_depth[gn] = group_depth.get(pp, -1) + 1

	group_rid = {}
	for g in cg_rows:
		gn = g["name"]
		if gn == "All Customer Groups":
			continue
		if not g_has.get(gn):
			continue
		depth = group_depth.get(gn, 0)
		pg = g.get("parent_customer_group") or ""
		prid = None
		if pg and pg != "All Customer Groups":
			prid = group_rid.get(pg)
		counter = counter + 1
		grid = "G" + str(counter)
		group_rid[gn] = grid
		a = g_agg[gn]
		rows.append({
			"row_id": grid, "parent_id": prid, "node_type": "group", "invoice": None,
			"label": gn, "mobile": "", "posting_date": None, "due_date": None,
			"overdue_days": None, "bills": a["bills"],
			"invoiced": a["invoiced"], "received": a["received"], "outstanding": a["outstanding"],
			"indent": depth,
		})
		pairs = []
		for pp2 in custs_by_group.get(gn, []):
			pairs.append((cust_agg[pp2]["outstanding"], pp2))
		pairs.sort(reverse=True)
		clist = []
		for pr in pairs:
			clist.append(pr[1])
		for p in clist:
			counter = counter + 1
			crid = "C" + str(counter)
			info = cust_info[p]
			a = cust_agg[p]
			rows.append({
				"row_id": crid, "parent_id": grid, "node_type": "customer", "invoice": None,
				"label": info["party_name"], "mobile": info["mobile"],
				"posting_date": None, "due_date": None, "overdue_days": None, "bills": a["bills"],
				"invoiced": a["invoiced"], "received": a["received"], "outstanding": a["outstanding"],
				"indent": depth + 1,
			})
			for r in cust_invs[p]:
				counter = counter + 1
				rows.append({
					"row_id": "I" + str(counter), "parent_id": crid, "node_type": "item",
					"invoice": r.get("invoice"), "label": r.get("invoice"), "mobile": "",
					"posting_date": r.get("posting_date"), "due_date": r.get("due_date"),
					"overdue_days": r.get("overdue_days"), "bills": None,
					"invoiced": frappe.utils.flt(r.get("invoiced")),
					"received": frappe.utils.flt(r.get("received")),
					"outstanding": frappe.utils.flt(r.get("outstanding")),
					"indent": depth + 2,
				})

	# fallback for customer groups not in tree
	known = set(cg_parent.keys())
	for gn in sorted(custs_by_group.keys()):
		if gn in known:
			continue
		counter = counter + 1
		grid = "G" + str(counter)
		a = {"invoiced": 0.0, "received": 0.0, "outstanding": 0.0, "bills": 0}
		for p in custs_by_group.get(gn, []):
			ca = cust_agg[p]
			for k in MET:
				a[k] = a[k] + ca[k]
			a["bills"] = a["bills"] + ca["bills"]
		rows.append({
			"row_id": grid, "parent_id": None, "node_type": "group", "invoice": None,
			"label": gn, "mobile": "", "posting_date": None, "due_date": None,
			"overdue_days": None, "bills": a["bills"],
			"invoiced": a["invoiced"], "received": a["received"], "outstanding": a["outstanding"],
			"indent": 0,
		})
		pairs = []
		for pp2 in custs_by_group.get(gn, []):
			pairs.append((cust_agg[pp2]["outstanding"], pp2))
		pairs.sort(reverse=True)
		clist = []
		for pr in pairs:
			clist.append(pr[1])
		for p in clist:
			counter = counter + 1
			crid = "C" + str(counter)
			info = cust_info[p]
			a = cust_agg[p]
			rows.append({
				"row_id": crid, "parent_id": grid, "node_type": "customer", "invoice": None,
				"label": info["party_name"], "mobile": info["mobile"],
				"posting_date": None, "due_date": None, "overdue_days": None, "bills": a["bills"],
				"invoiced": a["invoiced"], "received": a["received"], "outstanding": a["outstanding"],
				"indent": 1,
			})
			for r in cust_invs[p]:
				counter = counter + 1
				rows.append({
					"row_id": "I" + str(counter), "parent_id": crid, "node_type": "item",
					"invoice": r.get("invoice"), "label": r.get("invoice"), "mobile": "",
					"posting_date": r.get("posting_date"), "due_date": r.get("due_date"),
					"overdue_days": r.get("overdue_days"), "bills": None,
					"invoiced": frappe.utils.flt(r.get("invoiced")),
					"received": frappe.utils.flt(r.get("received")),
					"outstanding": frappe.utils.flt(r.get("outstanding")),
					"indent": 2,
				})

# ---- summary cards ----
g_out = 0.0
g_overdue = 0.0
for r in inv_rows:
	g_out = g_out + frappe.utils.flt(r.get("outstanding"))
	if (r.get("overdue_days") or 0) > 0:
		g_overdue = g_overdue + frappe.utils.flt(r.get("outstanding"))

report_summary = [
	{"value": g_out, "label": "Total Outstanding", "datatype": "Currency", "currency": "INR", "indicator": "orange"},
	{"value": g_overdue, "label": "Overdue Outstanding", "datatype": "Currency", "currency": "INR", "indicator": "red"},
	{"value": len(inv_rows), "label": "Pending Invoices", "datatype": "Int", "indicator": "blue"},
	{"value": len(cust_invs), "label": "Customers", "datatype": "Int", "indicator": "grey"},
]

data = (columns, rows, None, None, report_summary)
