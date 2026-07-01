# Store Shift Report — standard Script Report (auto-converted from safe_exec DB script)
import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	# Store Shift Report — DB-stored Script Report (safe_exec / RestrictedPython compatible)
	# Contract: receives `filters`; must set `data` = (columns, rows, message, chart, report_summary)
	#
	# IMPORTANT safe_exec rule: functions defined here do NOT capture module-level
	# variables (no closures). Everything that touches the data is inlined.
	#
	# Shows store stock movements (Inward receipts + Outward issues) during a chosen
	# shift on a chosen date. Mirrors the "Stores Daily Shift Report" sheet so the
	# in-charge can pick a date + shift, then print or export to Excel.

	shift_date = filters.get("shift_date") or frappe.utils.nowdate()
	shift = filters.get("shift") or "Full Day"
	company = filters.get("company") or frappe.db.get_default("Company")
	movement = filters.get("movement") or "All"

	# ---- shift -> [start_dt, end_dt] window (Shift C crosses midnight into next day) ----
	next_day = frappe.utils.add_days(shift_date, 1)
	if shift == "A":
		start_dt = shift_date + " 06:00:00"
		end_dt = shift_date + " 13:59:59"
	elif shift == "B":
		start_dt = shift_date + " 14:00:00"
		end_dt = shift_date + " 21:59:59"
	elif shift == "C":
		start_dt = shift_date + " 22:00:00"
		end_dt = str(next_day) + " 05:59:59"
	else:
		start_dt = shift_date + " 00:00:00"
		end_dt = shift_date + " 23:59:59"

	# ---- filter conditions ----
	cond = ""
	params = {"co": company, "start": start_dt, "end": end_dt}

	# Warehouse (tree-inclusive: a parent/group warehouse includes all its children)
	if filters.get("warehouse"):
		wlr = frappe.db.get_value("Warehouse", filters.get("warehouse"), ["lft", "rgt"])
		if wlr and wlr[0] is not None:
			cond = cond + " AND sle.warehouse IN (SELECT w2.name FROM `tabWarehouse` w2 WHERE w2.lft >= %(wl)s AND w2.rgt <= %(wr)s)"
			params["wl"] = wlr[0]
			params["wr"] = wlr[1]
		else:
			cond = cond + " AND sle.warehouse = %(wh)s"
			params["wh"] = filters.get("warehouse")

	# Item Group (tree-inclusive)
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

	# Movement direction
	if movement == "Inward":
		cond = cond + " AND sle.actual_qty > 0"
	elif movement == "Outward":
		cond = cond + " AND sle.actual_qty < 0"

	query = (
		"SELECT sle.posting_date AS posting_date, sle.posting_time AS posting_time, "
		"sle.voucher_type AS voucher_type, sle.voucher_no AS voucher_no, "
		"sle.item_code AS item_code, i.item_name AS item_name, i.stock_uom AS uom, "
		"i.item_group AS item_group, sle.warehouse AS warehouse, "
		"sle.actual_qty AS actual_qty, sle.qty_after_transaction AS balance_qty "
		"FROM `tabStock Ledger Entry` sle "
		"INNER JOIN `tabItem` i ON i.name = sle.item_code "
		"WHERE sle.is_cancelled = 0 AND sle.company = %(co)s "
		"AND TIMESTAMP(sle.posting_date, sle.posting_time) >= %(start)s "
		"AND TIMESTAMP(sle.posting_date, sle.posting_time) <= %(end)s" + cond + " "
		"ORDER BY sle.posting_date, sle.posting_time, sle.voucher_no"
	)
	moves = frappe.db.sql(query, params, as_dict=True)

	# ---- party / source lookup per voucher (batched, no N+1, all inlined) ----
	by_type = {}
	for m in moves:
		by_type.setdefault(m["voucher_type"], set()).add(m["voucher_no"])

	party_map = {}
	specs = [
		["Purchase Receipt", "supplier_name"],
		["Purchase Invoice", "supplier_name"],
		["Delivery Note", "customer_name"],
		["Sales Invoice", "customer_name"],
		["Stock Entry", "stock_entry_type"],
	]
	for spec in specs:
		dt = spec[0]
		field = spec[1]
		names = by_type.get(dt)
		if names:
			for d in frappe.get_all(dt, filters={"name": ["in", list(names)]}, fields=["name", field]):
				party_map[dt + "::" + d["name"]] = d.get(field)

	# ---- split into inward / outward ----
	inward = []
	outward = []
	for m in moves:
		q = float(m.get("actual_qty") or 0)
		if q > 0:
			inward.append(m)
		elif q < 0:
			outward.append(m)

	rows = []
	tot_in = 0.0
	tot_out = 0.0

	if movement != "Outward":
		rows.append({"row_type": "section", "voucher_type": "MATERIAL RECEIPTS (INWARD)"})
		s = 0.0
		for m in inward:
			q = float(m.get("actual_qty") or 0)
			rows.append({
				"row_type": "data",
				"posting_time": m.get("posting_time"),
				"voucher_type": m.get("voucher_type"),
				"voucher_no": m.get("voucher_no"),
				"party": party_map.get(m["voucher_type"] + "::" + m["voucher_no"]) or "",
				"item_code": m.get("item_code"),
				"item_name": m.get("item_name"),
				"warehouse": m.get("warehouse"),
				"in_qty": q,
				"out_qty": 0.0,
				"balance_qty": float(m.get("balance_qty") or 0),
				"uom": m.get("uom"),
			})
			s = s + q
		tot_in = s
		rows.append({"row_type": "subtotal", "party": "Total Received", "in_qty": s, "out_qty": 0.0})

	if movement != "Inward":
		rows.append({"row_type": "section", "voucher_type": "MATERIAL ISSUES (OUTWARD)"})
		s = 0.0
		for m in outward:
			q = -float(m.get("actual_qty") or 0)
			rows.append({
				"row_type": "data",
				"posting_time": m.get("posting_time"),
				"voucher_type": m.get("voucher_type"),
				"voucher_no": m.get("voucher_no"),
				"party": party_map.get(m["voucher_type"] + "::" + m["voucher_no"]) or "",
				"item_code": m.get("item_code"),
				"item_name": m.get("item_name"),
				"warehouse": m.get("warehouse"),
				"in_qty": 0.0,
				"out_qty": q,
				"balance_qty": float(m.get("balance_qty") or 0),
				"uom": m.get("uom"),
			})
			s = s + q
		tot_out = s
		rows.append({"row_type": "subtotal", "party": "Total Issued", "in_qty": 0.0, "out_qty": s})

	# ---- summary cards ----
	report_summary = [
		{"value": len(inward), "label": "Receipt Lines", "datatype": "Int", "indicator": "blue"},
		{"value": tot_in, "label": "Qty Received", "datatype": "Float", "indicator": "blue"},
		{"value": len(outward), "label": "Issue Lines", "datatype": "Int", "indicator": "orange"},
		{"value": tot_out, "label": "Qty Issued", "datatype": "Float", "indicator": "orange"},
	]

	columns = [
		{"fieldname": "row_type", "label": "RT", "fieldtype": "Data", "hidden": 1},
		{"fieldname": "posting_time", "label": "Time", "fieldtype": "Data", "width": 80},
		{"fieldname": "voucher_type", "label": "Voucher Type", "fieldtype": "Data", "width": 150},
		{"fieldname": "voucher_no", "label": "Voucher / GRN No", "fieldtype": "Data", "width": 160},
		{"fieldname": "party", "label": "Supplier / Department", "fieldtype": "Data", "width": 180},
		{"fieldname": "item_code", "label": "Item Code", "fieldtype": "Link", "options": "Item", "width": 130},
		{"fieldname": "item_name", "label": "Item Description", "fieldtype": "Data", "width": 230},
		{"fieldname": "warehouse", "label": "Warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"fieldname": "in_qty", "label": "Qty Received", "fieldtype": "Float", "precision": 3, "width": 120},
		{"fieldname": "out_qty", "label": "Qty Issued", "fieldtype": "Float", "precision": 3, "width": 120},
		{"fieldname": "balance_qty", "label": "Balance In Stock", "fieldtype": "Float", "precision": 3, "width": 130},
		{"fieldname": "uom", "label": "UOM", "fieldtype": "Data", "width": 70},
	]

	data = (columns, rows, None, None, report_summary)
	return data
