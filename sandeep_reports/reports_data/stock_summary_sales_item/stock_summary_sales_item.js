// Tally-style Stock Summary (Sales Item) — Warehouse > Item Group > Sales Item
frappe.query_reports["Stock Summary (Sales Item)"] = {
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
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: (function () {
				var parts = frappe.datetime.get_today().split("-");
				var y = parseInt(parts[0]), m = parseInt(parts[1]);
				return (m >= 4 ? y : y - 1) + "-04-01";
			})(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: function () {
				var c = frappe.query_report.get_filter_value("company");
				return { filters: c ? { company: c } : {} };
			},
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "sales_item",
			label: __("Sales Item"),
			fieldtype: "Link",
			options: "Sales Item",
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Link",
			options: "Brand",
		},
		{
			fieldname: "only_closing",
			label: __("Only With Closing Stock"),
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
			if (data.node_type === "warehouse") {
				value = "<span style='font-weight:700;font-size:13px;color:#1a3c5e'>"
					+ "🏬 " + (data.label || "") + "</span>";
			} else if (data.node_type === "group") {
				value = "<span style='font-weight:600;font-size:12px;color:#2c5282'>"
					+ "📁 " + (data.label || "") + "</span>";
			} else if (data.node_type === "sales_item") {
				value = "<span style='color:#1a73e8;font-weight:500'>"
					+ "📦 " + (data.label || "") + "</span>";
			}
		}

		if (column.fieldname === "in_val" && value) {
			value = "<span style='color:#2980b9'>" + value + "</span>";
		}
		if (column.fieldname === "out_val" && value) {
			value = "<span style='color:#e67e22'>" + value + "</span>";
		}
		if (column.fieldname === "close_val") {
			var amt = parseFloat(data.close_val) || 0;
			var display = value || frappe.format(amt, { fieldtype: "Currency" });
			var col = amt < 0 ? "#c0392b" : "#27ae60";
			value = "<span style='color:" + col + ";font-weight:" + (data.node_type !== "sales_item" ? "700" : "500") + "'>" + display + "</span>";
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
			function fnum(val, dec) {
				var n = parseFloat(val) || 0;
				return n.toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec });
			}
			var heads = ["Particulars", "Opening Qty", "Opening Value", "Inward Qty", "Inward Value",
				"Outward Qty", "Outward Value", "Closing Qty", "Closing Value"];
			var html = '<html xmlns:o="urn:schemas-microsoft-com:office:office" '
				+ 'xmlns:x="urn:schemas-microsoft-com:office:excel" '
				+ 'xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="UTF-8">'
				+ '<!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet>'
				+ '<x:Name>Stock Summary</x:Name><x:WorksheetOptions><x:DisplayGridlines/>'
				+ '</x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]-->'
				+ '</head><body><table border="1" style="border-collapse:collapse;font-family:Calibri;font-size:11pt;">';
			html += '<tr style="background-color:#1a3c5e;color:#fff;font-weight:bold;">';
			heads.forEach(function (h, i) {
				html += '<td style="padding:6px 10px;' + (i ? "text-align:right;" : "") + '">' + h + '</td>';
			});
			html += '</tr>';
			data.forEach(function (r) {
				var indent = r.indent || 0;
				var pad = (indent * 18) + "px";
				var label = (r.label || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
				var grp = r.node_type !== "sales_item";
				var bg = r.node_type === "warehouse" ? "#dce6f1" : (r.node_type === "group" ? "#eaf2fb" : "#ffffff");
				var fw = grp ? "bold" : "normal";
				html += '<tr style="background-color:' + bg + ';">';
				html += '<td style="padding:4px 8px;padding-left:' + pad + ';font-weight:' + fw + ';color:#1a3c5e;">' + label + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;">' + fnum(r.opening_qty, 3) + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;font-weight:' + fw + ';">' + fnum(r.opening_val, 2) + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;">' + fnum(r.in_qty, 3) + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;font-weight:' + fw + ';">' + fnum(r.in_val, 2) + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;">' + fnum(r.out_qty, 3) + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;font-weight:' + fw + ';">' + fnum(r.out_val, 2) + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;">' + fnum(r.close_qty, 3) + '</td>';
				html += '<td style="padding:4px 8px;text-align:right;font-weight:' + fw + ';">' + fnum(r.close_val, 2) + '</td>';
				html += '</tr>';
			});
			html += '</table></body></html>';
			var blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8" });
			var url = URL.createObjectURL(blob);
			var a = document.createElement("a");
			var as_on = frappe.query_report.get_filter_value("to_date") || frappe.datetime.get_today();
			a.href = url;
			a.download = "Stock_Summary_SalesItem_" + as_on + ".xls";
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		});
	},
};
