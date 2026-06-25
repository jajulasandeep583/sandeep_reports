# Idempotent installer for the sandeep_reports Script Reports.
# Run inside a bench console (so `frappe` is available):
#
#   bench --site <site> console <<'EOF'
#   import os; os.environ["SANDEEP_REPORTS_DIR"] = "/abs/path/to/sandeep_reports"
#   exec(open(os.path.join(os.environ["SANDEEP_REPORTS_DIR"], "install.py")).read())
#   EOF
#
# Kept as flat, module-level code on purpose (RestrictedPython/console exec scoping).
import os
import json

REPO_DIR = os.environ.get("SANDEEP_REPORTS_DIR") or os.getcwd()
manifest = json.loads(open(os.path.join(REPO_DIR, "manifest.json"), encoding="utf-8").read())

for entry in manifest:
	slug = entry["slug"]
	d = os.path.join(REPO_DIR, "reports", slug)
	meta = json.loads(open(os.path.join(d, slug + ".json"), encoding="utf-8").read())
	py = open(os.path.join(d, slug + ".py"), encoding="utf-8").read()
	js = open(os.path.join(d, slug + ".js"), encoding="utf-8").read()

	if frappe.db.exists("Report", meta["report_name"]):
		doc = frappe.get_doc("Report", meta["report_name"])
	else:
		doc = frappe.new_doc("Report")
		doc.report_name = meta["report_name"]
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
	print("installed:", doc.name)

frappe.db.commit()
print("ALL DONE")
