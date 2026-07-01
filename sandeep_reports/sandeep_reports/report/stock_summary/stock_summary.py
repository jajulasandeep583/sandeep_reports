# Stock Summary — standard Script Report (auto-converted from safe_exec DB script)
import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	# Stock Summary — DB-stored Script Report (safe_exec / RestrictedPython compatible)
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

	# Item
	if filters.get("item_code"):
		cond = cond + " AND sle.item_code = %(item_code)s"
		params["item_code"] = filters.get("item_code")

	# Brand
	if filters.get("brand"):
		cond = cond + " AND i.brand = %(brand)s"
		params["brand"] = filters.get("brand")

	# HAVING: by default keep any row with movement OR balance; if "only_closing" is
	# ticked, keep only rows that still carry a closing balance.
	if filters.get("only_closing"):
		having = "HAVING ABS(close_qty) > 0.001 OR ABS(close_val) > 0.01 "
	else:
		having = ("HAVING ABS(close_qty) > 0.001 OR ABS(opening_qty) > 0.001 OR ABS(in_qty) > 0.001 OR ABS(out_qty) > 0.001 "
			"OR ABS(close_val) > 0.01 OR ABS(opening_val) > 0.01 OR ABS(in_val) > 0.01 OR ABS(out_val) > 0.01 ")

	# Inward/Outward VALUE is keyed off stock_value_difference sign (NOT actual_qty),
	# so zero-qty revaluations (Stock Reconciliation / rate changes) are captured too.
	# This guarantees: Closing Value = Opening Value + Inward Value - Outward Value.
	# Inward/Outward QTY stays keyed off actual_qty sign (qty=0 entries add no qty).
	query = (
		"SELECT sle.warehouse AS warehouse, sle.item_code AS item_code, i.item_name AS item_name, "
		"i.item_group AS item_group, "
		"SUM(CASE WHEN sle.posting_date < %(fd)s THEN sle.actual_qty ELSE 0 END) AS opening_qty, "
		"SUM(CASE WHEN sle.posting_date < %(fd)s THEN sle.stock_value_difference ELSE 0 END) AS opening_val, "
		"SUM(CASE WHEN sle.actual_qty > 0 AND sle.posting_date >= %(fd)s THEN sle.actual_qty ELSE 0 END) AS in_qty, "
		"SUM(CASE WHEN sle.stock_value_difference > 0 AND sle.posting_date >= %(fd)s THEN sle.stock_value_difference ELSE 0 END) AS in_val, "
		"ABS(SUM(CASE WHEN sle.actual_qty < 0 AND sle.posting_date >= %(fd)s THEN sle.actual_qty ELSE 0 END)) AS out_qty, "
		"ABS(SUM(CASE WHEN sle.stock_value_difference < 0 AND sle.posting_date >= %(fd)s THEN sle.stock_value_difference ELSE 0 END)) AS out_val, "
		"SUM(sle.actual_qty) AS close_qty, "
		"SUM(sle.stock_value_difference) AS close_val "
		"FROM `tabStock Ledger Entry` sle "
		"INNER JOIN `tabItem` i ON i.name = sle.item_code "
		"WHERE sle.is_cancelled = 0 AND sle.company = %(co)s AND sle.posting_date <= %(td)s" + cond + " "
		"GROUP BY sle.warehouse, sle.item_code "
		+ having +
		"ORDER BY sle.warehouse, i.item_name"
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

				gitems = sorted(items_by_group.get(gname, []), key=lambda x: (x.get("item_name") or x.get("item_code") or ""))
				for it in gitems:
					counter = counter + 1
					irid = "I" + str(counter)
					nm = it.get("item_name") or it.get("item_code")
					ic = it.get("item_code")
					label = nm
					if nm and ic and nm != ic:
						label = nm + " (" + ic + ")"
					irow = {"row_id": irid, "parent_id": grid, "node_type": "item",
						"label": label, "indent": base + eff_depth + 1,
						"item_code": ic, "warehouse": it.get("warehouse")}
					for k in METRICS:
						irow[k] = float(it.get(k) or 0)
					rows.append(irow)

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
