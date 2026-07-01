# Stock Summary Sales Item — standard Script Report (auto-converted from safe_exec DB script)
import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	# Stock Summary (Sales Item) — DB-stored Script Report (safe_exec / RestrictedPython compatible)
	# Tree = Warehouse > Item Group (nested) > Sales Item (leaf).
	# The Sales Item is the bottom line: its qty/value is the sum of every item that
	# is mapped to that sales_item within the item group + warehouse. Each Item has
	# exactly one sales_item, so there is no double counting.
	# Contract: receives `filters`; must set `data` = (columns, rows, message, chart, report_summary)
	to_date = filters.get("to_date") or frappe.utils.nowdate()
	company = filters.get("company") or frappe.db.get_default("Company")
	from_date = filters.get("from_date")
	if not from_date:
		fy_start = frappe.db.get_value(
			"Fiscal Year",
			{"year_start_date": ("<=", to_date), "year_end_date": (">=", to_date)},
			"year_start_date",
		)
		if fy_start:
			from_date = str(fy_start)
		else:
			from_date = to_date

	METRICS = ["opening_qty", "opening_val", "in_qty", "in_val", "out_qty", "out_val", "close_qty", "close_val"]


	def newm():
		return {"opening_qty": 0.0, "opening_val": 0.0, "in_qty": 0.0, "in_val": 0.0,
			"out_qty": 0.0, "out_val": 0.0, "close_qty": 0.0, "close_val": 0.0}


	# ---- filters ----
	cond = ""
	params = {"fd": from_date, "td": to_date, "co": company}

	# Warehouse (tree-inclusive: selecting a parent/group warehouse includes all children)
	if filters.get("warehouse"):
		wlr = frappe.db.get_value("Warehouse", filters.get("warehouse"), ["lft", "rgt"])
		if wlr and wlr[0] is not None:
			cond = cond + " AND sle.warehouse IN (SELECT w2.name FROM `tabWarehouse` w2 WHERE w2.lft >= %(wl)s AND w2.rgt <= %(wr)s)"
			params["wl"] = wlr[0]
			params["wr"] = wlr[1]
		else:
			cond = cond + " AND sle.warehouse = %(wh)s"
			params["wh"] = filters.get("warehouse")

	# Item Group (tree-inclusive: selecting a parent group includes all sub-groups)
	if filters.get("item_group"):
		glr = frappe.db.get_value("Item Group", filters.get("item_group"), ["lft", "rgt"])
		if glr and glr[0] is not None:
			cond = cond + " AND i.item_group IN (SELECT g2.name FROM `tabItem Group` g2 WHERE g2.lft >= %(igl)s AND g2.rgt <= %(igr)s)"
			params["igl"] = glr[0]
			params["igr"] = glr[1]
		else:
			cond = cond + " AND i.item_group = %(ig)s"
			params["ig"] = filters.get("item_group")

	# Sales Item (replaces the Item filter of the original report)
	if filters.get("sales_item"):
		cond = cond + " AND i.sales_item = %(sales_item)s"
		params["sales_item"] = filters.get("sales_item")

	# Brand
	if filters.get("brand"):
		cond = cond + " AND i.brand = %(brand)s"
		params["brand"] = filters.get("brand")

	# HAVING: by default keep any leaf with movement OR balance; if "only_closing" is
	# ticked, keep only leaves that still carry a closing balance.
	if filters.get("only_closing"):
		having = "HAVING ABS(close_qty) > 0.001 OR ABS(close_val) > 0.01 "
	else:
		having = ("HAVING ABS(close_qty) > 0.001 OR ABS(opening_qty) > 0.001 OR ABS(in_qty) > 0.001 OR ABS(out_qty) > 0.001 "
			"OR ABS(close_val) > 0.01 OR ABS(opening_val) > 0.01 OR ABS(in_val) > 0.01 OR ABS(out_val) > 0.01 ")

	# Leaf = one row per (warehouse, item_group, sales_item). Items with no sales_item
	# bucket under "— No Sales Item —". Label comes from Sales Item.sales_item_name.
	#
	# This report must reconcile EXACTLY to ERPNext's standard "Stock Balance" report.
	# Two things are required for that (both were wrong with a naive SUM(actual_qty)):
	#  (1) QTY change per entry is derived the same way Stock Balance does: for a Stock
	#      Reconciliation the change is the JUMP in qty_after_transaction (a reco sets an
	#      absolute physical count and records actual_qty = 0, so SUM(actual_qty) silently
	#      drops every reco-set quantity); for every other voucher it is plain actual_qty.
	#      `qty_delta` below encodes exactly that (LAG = previous running balance).
	#  (2) Item+warehouse rows whose CLOSING balance (qty AND value) is zero are hidden,
	#      mirroring Stock Balance's default (include_zero_stock_items off). An item that
	#      came fully in and went fully out within the period nets to zero closing and
	#      must NOT inflate the Inward/Outward flow totals. The inner HAVING does this at
	#      the (item, warehouse) grain BEFORE rolling up to the Sales Item leaf.
	# VALUE always uses stock_value_difference (reco populates it correctly), so
	# Closing Value = Opening + Inward - Outward and matches Stock Balance to the paisa.
	query = (
		"SELECT iw.warehouse AS warehouse, iw.item_group AS item_group, iw.si_key AS si_key, iw.si_label AS si_label, "
		"SUM(iw.opening_qty) AS opening_qty, SUM(iw.opening_val) AS opening_val, "
		"SUM(iw.in_qty) AS in_qty, SUM(iw.in_val) AS in_val, "
		"SUM(iw.out_qty) AS out_qty, SUM(iw.out_val) AS out_val, "
		"SUM(iw.close_qty) AS close_qty, SUM(iw.close_val) AS close_val "
		"FROM ("
			"SELECT d.warehouse AS warehouse, d.item_group AS item_group, d.si_key AS si_key, d.si_label AS si_label, "
			"SUM(CASE WHEN d.posting_date < %(fd)s THEN d.qty_delta ELSE 0 END) AS opening_qty, "
			"SUM(CASE WHEN d.posting_date < %(fd)s THEN d.val_delta ELSE 0 END) AS opening_val, "
			"SUM(CASE WHEN d.qty_delta > 0 AND d.posting_date >= %(fd)s THEN d.qty_delta ELSE 0 END) AS in_qty, "
			"SUM(CASE WHEN d.val_delta > 0 AND d.posting_date >= %(fd)s THEN d.val_delta ELSE 0 END) AS in_val, "
			"ABS(SUM(CASE WHEN d.qty_delta < 0 AND d.posting_date >= %(fd)s THEN d.qty_delta ELSE 0 END)) AS out_qty, "
			"ABS(SUM(CASE WHEN d.val_delta < 0 AND d.posting_date >= %(fd)s THEN d.val_delta ELSE 0 END)) AS out_val, "
			"SUM(d.qty_delta) AS close_qty, SUM(d.val_delta) AS close_val "
			"FROM ("
				"SELECT sle.item_code AS item_code, sle.warehouse AS warehouse, sle.posting_date AS posting_date, "
				"i.item_group AS item_group, COALESCE(i.sales_item, '__NOSI__') AS si_key, "
				"COALESCE(si.sales_item_name, i.sales_item, '— No Sales Item —') AS si_label, "
				"CASE WHEN sle.voucher_type = 'Stock Reconciliation' AND (sle.batch_no IS NULL OR sle.batch_no = '') "
					"THEN sle.qty_after_transaction - COALESCE(LAG(sle.qty_after_transaction) OVER ("
						"PARTITION BY sle.item_code, sle.warehouse "
						"ORDER BY sle.posting_date, sle.posting_time, sle.creation), 0) "
					"ELSE sle.actual_qty END AS qty_delta, "
				"sle.stock_value_difference AS val_delta "
				"FROM `tabStock Ledger Entry` sle "
				"INNER JOIN `tabItem` i ON i.name = sle.item_code "
				"LEFT JOIN `tabSales Item` si ON si.name = i.sales_item "
				"WHERE sle.is_cancelled = 0 AND sle.company = %(co)s AND sle.posting_date <= %(td)s" + cond + " "
			") d "
			"GROUP BY d.item_code, d.warehouse, d.item_group, d.si_key, d.si_label "
			"HAVING ABS(SUM(d.qty_delta)) > 0.0001 OR ABS(SUM(d.val_delta)) > 0.0001 "
		") iw "
		"GROUP BY iw.warehouse, iw.item_group, iw.si_key "
		+ having +
		"ORDER BY iw.warehouse, iw.item_group, iw.si_label"
	)
	data_rows = frappe.db.sql(query, params, as_dict=True)

	items_by_wh = {}
	for r in data_rows:
		items_by_wh.setdefault(r["warehouse"], []).append(r)

	# ---- item group tree ----
	ig_rows = frappe.db.sql("select name, parent_item_group from `tabItem Group` order by lft", as_dict=True)
	ig_order = []
	ig_parent = {}
	ig_children = {}
	for g in ig_rows:
		ig_order.append(g["name"])
		p = g["parent_item_group"] or ""
		ig_parent[g["name"]] = p
		if p:
			ig_children.setdefault(p, []).append(g["name"])

	# ---- warehouse tree ----
	wh_rows = frappe.db.sql("select name, parent_warehouse from `tabWarehouse` where company=%(co)s order by lft", params, as_dict=True)
	wh_order = []
	wh_parent = {}
	wh_children = {}
	for w in wh_rows:
		wh_order.append(w["name"])
		p = w["parent_warehouse"] or ""
		wh_parent[w["name"]] = p
		if p:
			wh_children.setdefault(p, []).append(w["name"])

	for whn in items_by_wh:
		if whn not in wh_parent:
			wh_parent[whn] = ""
			wh_order.append(whn)

	# ---- warehouse aggregation (bottom-up) ----
	wh_agg = {}
	wh_has = {}
	for name in wh_order[::-1]:
		agg = newm()
		hd = False
		for it in items_by_wh.get(name, []):
			for k in METRICS:
				agg[k] = agg[k] + float(it.get(k) or 0)
			hd = True
		for ch in wh_children.get(name, []):
			if wh_has.get(ch):
				ca = wh_agg[ch]
				for k in METRICS:
					agg[k] = agg[k] + ca[k]
				hd = True
		wh_agg[name] = agg
		wh_has[name] = hd

	rows = []
	counter = 0

	# ---- pre-order traversal of warehouse tree (explicit stack) ----
	stack = []
	roots = []
	for w in wh_order:
		if not wh_parent.get(w):
			roots.append(w)
	for w in roots[::-1]:
		stack.append([w, None, 0])

	while stack:
		top = stack.pop()
		wname = top[0]
		parent_rid = top[1]
		indent = top[2]
		if not wh_has.get(wname):
			continue
		counter = counter + 1
		wrid = "W" + str(counter)
		agg = wh_agg[wname]
		wrow = {"row_id": wrid, "parent_id": parent_rid, "node_type": "warehouse",
			"label": wname, "indent": indent, "item_code": None, "warehouse": None}
		for k in METRICS:
			wrow[k] = agg[k]
		rows.append(wrow)

		items = items_by_wh.get(wname)
		if items:
			# bucket this warehouse's leaf rows by their immediate item group
			items_by_group = {}
			for it in items:
				grp = it.get("item_group") or "Ungrouped"
				items_by_group.setdefault(grp, []).append(it)

			g_agg = {}
			g_has = {}
			for gname in ig_order[::-1]:
				ga = newm()
				ghd = False
				for it in items_by_group.get(gname, []):
					for k in METRICS:
						ga[k] = ga[k] + float(it.get(k) or 0)
					ghd = True
				for ch in ig_children.get(gname, []):
					if g_has.get(ch):
						cca = g_agg[ch]
						for k in METRICS:
							ga[k] = ga[k] + cca[k]
						ghd = True
				g_agg[gname] = ga
				g_has[gname] = ghd

			emit_order = []
			for gname in ig_order:
				emit_order.append(gname)
			if "Ungrouped" in items_by_group and "Ungrouped" not in g_agg:
				ga = newm()
				for it in items_by_group["Ungrouped"]:
					for k in METRICS:
						ga[k] = ga[k] + float(it.get(k) or 0)
				g_agg["Ungrouped"] = ga
				g_has["Ungrouped"] = True
				emit_order.append("Ungrouped")

			base = indent + 1
			ginfo_rid = {}
			ginfo_depth = {}
			for gname in emit_order:
				if gname == "All Item Groups":
					continue
				if not g_has.get(gname):
					continue
				pg = ig_parent.get(gname) or ""
				if pg in ginfo_rid:
					parent_g_rid = ginfo_rid[pg]
					eff_depth = ginfo_depth[pg] + 1
				else:
					parent_g_rid = wrid
					eff_depth = 0
				counter = counter + 1
				grid = "G" + str(counter)
				ginfo_rid[gname] = grid
				ginfo_depth[gname] = eff_depth
				ga = g_agg[gname]
				grow = {"row_id": grid, "parent_id": parent_g_rid, "node_type": "group",
					"label": gname, "indent": base + eff_depth, "item_code": None, "warehouse": None}
				for k in METRICS:
					grow[k] = ga[k]
				rows.append(grow)

				# leaf rows = the sales-item aggregates that sit directly under this group
				sitems = sorted(items_by_group.get(gname, []), key=lambda x: (x.get("si_label") or ""))
				for it in sitems:
					counter = counter + 1
					srid = "S" + str(counter)
					srow = {"row_id": srid, "parent_id": grid, "node_type": "sales_item",
						"label": it.get("si_label") or "— No Sales Item —",
						"indent": base + eff_depth + 1, "item_code": None, "warehouse": None}
					for k in METRICS:
						srow[k] = float(it.get(k) or 0)
					rows.append(srow)

		kids = wh_children.get(wname) or []
		for ch in kids[::-1]:
			stack.append([ch, wrid, indent + 1])

	# ---- summary cards ----
	tot = newm()
	for it in data_rows:
		for k in METRICS:
			tot[k] = tot[k] + float(it.get(k) or 0)

	report_summary = [
		{"value": tot["opening_val"], "label": "Opening Value", "datatype": "Currency", "currency": "INR", "indicator": "grey"},
		{"value": tot["in_val"], "label": "Inward Value", "datatype": "Currency", "currency": "INR", "indicator": "blue"},
		{"value": tot["out_val"], "label": "Outward Value", "datatype": "Currency", "currency": "INR", "indicator": "orange"},
		{"value": tot["close_val"], "label": "Closing Value", "datatype": "Currency", "currency": "INR", "indicator": "green"},
	]

	columns = [
		{"fieldname": "row_id", "label": "Row ID", "fieldtype": "Data", "hidden": 1},
		{"fieldname": "parent_id", "label": "Parent ID", "fieldtype": "Data", "hidden": 1},
		{"fieldname": "node_type", "label": "Type", "fieldtype": "Data", "hidden": 1},
		{"fieldname": "item_code", "label": "Item Code", "fieldtype": "Data", "hidden": 1},
		{"fieldname": "warehouse", "label": "Warehouse", "fieldtype": "Data", "hidden": 1},
		{"fieldname": "label", "label": "Particulars", "fieldtype": "Data", "width": 360},
		{"fieldname": "opening_qty", "label": "Opening Qty", "fieldtype": "Float", "precision": 3, "width": 110},
		{"fieldname": "opening_val", "label": "Opening Value", "fieldtype": "Currency", "width": 130},
		{"fieldname": "in_qty", "label": "Inward Qty", "fieldtype": "Float", "precision": 3, "width": 110},
		{"fieldname": "in_val", "label": "Inward Value", "fieldtype": "Currency", "width": 130},
		{"fieldname": "out_qty", "label": "Outward Qty", "fieldtype": "Float", "precision": 3, "width": 110},
		{"fieldname": "out_val", "label": "Outward Value", "fieldtype": "Currency", "width": 130},
		{"fieldname": "close_qty", "label": "Closing Qty", "fieldtype": "Float", "precision": 3, "width": 110},
		{"fieldname": "close_val", "label": "Closing Value", "fieldtype": "Currency", "width": 140},
	]

	data = (columns, rows, None, None, report_summary)
	return data
