// Receivable Follow-up — lightweight collections report
frappe.query_reports["Receivable Follow-up"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: "Customer Group\nCustomer\nVoucher",
			default: "Customer Group",
		},
		{
			fieldname: "posting_from_date",
			label: __("Posting From"),
			fieldtype: "Date",
		},
		{
			fieldname: "posting_to_date",
			label: __("Posting To"),
			fieldtype: "Date",
		},
		{
			fieldname: "due_from_date",
			label: __("Due From"),
			fieldtype: "Date",
		},
		{
			fieldname: "due_to_date",
			label: __("Due To"),
			fieldtype: "Date",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "customer_group",
			label: __("Customer Group"),
			fieldtype: "Link",
			options: "Customer Group",
		},
		{
			fieldname: "only_overdue",
			label: __("Only Overdue"),
			fieldtype: "Check",
			default: 0,
		},
	],
	tree: true,
	name_field: "row_id",
	parent_field: "parent_id",
	initial_depth: 1,

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		if (column.fieldname === "label") {
			if (data.node_type === "group") {
				value = "<span style='font-weight:700;font-size:13px;color:#1a3c5e'>" + (data.label || "") + "</span>";
			} else if (data.node_type === "customer") {
				value = "<span style='font-weight:600;font-size:12px;color:#2c5282'>" + (data.label || "") + "</span>";
			} else if (data.node_type === "item") {
				var url = "/app/sales-invoice/" + encodeURIComponent(data.invoice || "");
				value = "<a href='" + url + "' style='color:#1a73e8;font-weight:500'>"
					+ (data.label || "") + " <span style='font-size:10px;opacity:0.7'>↗</span></a>";
			}
		}
		if (column.fieldname === "mobile" && value) {
			value = "<a href='tel:" + (data.mobile || "") + "' style='color:#0b8043'>" + value + "</a>";
		}
		if (column.fieldname === "overdue_days") {
			var od = parseInt(data.overdue_days) || 0;
			if (od > 0) {
				var col = od > 60 ? "#c0392b" : (od > 30 ? "#e67e22" : "#d4a107");
				value = "<span style='color:" + col + ";font-weight:600'>" + od + "</span>";
			} else if (data.node_type === "item") {
				value = "<span style='color:#27ae60'>0</span>";
			}
		}
		if (column.fieldname === "outstanding") {
			var amt = parseFloat(data.outstanding) || 0;
			var disp = value || frappe.format(amt, { fieldtype: "Currency" });
			value = "<span style='color:#e67e22;font-weight:" + (data.node_type !== "item" ? "700" : "500") + "'>" + disp + "</span>";
		}
		return value;
	},

	onload: function (report) {
		report.page.add_inner_button(__("Export to Excel"), function () {
			const data = frappe.query_report.data;
			if (!data || !data.length) {
				frappe.msgprint(__("No data to export."));
				return;
			}
			function fnum(val) {
				var n = parseFloat(val) || 0;
				return n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
			}
			function esc(s) {
				return (s == null ? "" : String(s)).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
			}
			var heads = ["Particulars", "Mobile", "Posting Date", "Due Date", "Overdue Days",
				"# Bills", "Invoice Amt", "Received", "Outstanding"];
			var html = '<html xmlns:o="urn:schemas-microsoft-com:office:office" '
				+ 'xmlns:x="urn:schemas-microsoft-com:office:excel" '
				+ 'xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="UTF-8">'
				+ '<!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet>'
				+ '<x:Name>Receivable Follow-up</x:Name><x:WorksheetOptions><x:DisplayGridlines/>'
				+ '</x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]-->'
				+ '</head><body><table border="1" style="border-collapse:collapse;font-family:Calibri;font-size:11pt;">';
			html += '<tr style="background-color:#1a3c5e;color:#fff;font-weight:bold;">';
			heads.forEach(function (h, i) {
				html += '<td style="padding:6px 10px;' + (i >= 5 ? "text-align:right;" : "") + '">' + h + '</td>';
			});
			html += '</tr>';
			data.forEach(function (r) {
				var indent = r.indent || 0;
				var pad = (indent * 18) + "px";
				var grp = r.node_type !== "item";
				var bg = r.node_type === "group" ? "#dce6f1" : (r.node_type === "customer" ? "#eaf2fb" : "#ffffff");
				var fw = grp ? "bold" : "normal";
				html += '<tr style="background-color:' + bg + ';">';
				html += '<td style="padding:4px 8px;padding-left:' + pad + ';font-weight:' + fw + ';color:#1a3c5e;">' + esc(r.label) + '</td>';
				html += '<td style="padding:4px 8px;">' + esc(r.mobile) + '</td>';
				html += '<td style="padding:4px 8px;">' + esc(r.posting_date) + '</td>';
				html += '<td style="padding:4px 8px;">' + esc(r.due_date) + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;">' + (r.overdue_days == null ? "" : r.overdue_days) + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;">' + (r.bills == null ? "" : r.bills) + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;font-weight:' + fw + ';">' + fnum(r.invoiced) + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;">' + fnum(r.received) + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;font-weight:' + fw + ';">' + fnum(r.outstanding) + '</td>';
				html += '</tr>';
			});
			html += '</table></body></html>';
			var blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8" });
			var url = URL.createObjectURL(blob);
			var a = document.createElement("a");
			var as_on = frappe.datetime.get_today();
			a.href = url;
			a.download = "Receivable_Followup_" + as_on + ".xls";
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		});
	},
};
