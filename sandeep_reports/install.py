# Creates / updates the bundled Script Reports on this site.
# Wired to after_install and after_migrate in hooks.py, and safe to re-run.
import os
import json

import frappe


def install_reports():
	base = os.path.join(os.path.dirname(__file__), "reports_data")
	manifest_path = os.path.join(base, "manifest.json")
	if not os.path.exists(manifest_path):
		return

	with open(manifest_path, encoding="utf-8") as f:
		manifest = json.loads(f.read())

	for entry in manifest:
		slug = entry["slug"]
		d = os.path.join(base, slug)
		with open(os.path.join(d, slug + ".json"), encoding="utf-8") as f:
			meta = json.loads(f.read())
		with open(os.path.join(d, slug + ".py"), encoding="utf-8") as f:
			py = f.read()
		with open(os.path.join(d, slug + ".js"), encoding="utf-8") as f:
			js = f.read()

		name = meta["report_name"]
		if frappe.db.exists("Report", name):
			doc = frappe.get_doc("Report", name)
		else:
			doc = frappe.new_doc("Report")
			doc.report_name = name

		doc.report_type = meta.get("report_type") or "Script Report"
		doc.ref_doctype = meta.get("ref_doctype")
		doc.module = meta.get("module") or "Accounts"
		doc.is_standard = "No"
		doc.disabled = 0
		doc.report_script = py
		doc.javascript = js
		doc.set("roles", [])
		for role in meta.get("roles") or []:
			if frappe.db.exists("Role", role):
				doc.append("roles", {"role": role})
		doc.save(ignore_permissions=True)
		frappe.msgprint("Installed report: " + name, alert=True)

	frappe.db.commit()
