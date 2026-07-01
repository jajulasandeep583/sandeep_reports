// Store Shift Report — pick a shift date + shift, see Inward/Outward store movements, print or export.
frappe.query_reports["Store Shift Report"] = {
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
			fieldname: "shift_date",
			label: __("Shift Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "shift",
			label: __("Shift"),
			fieldtype: "Select",
			options: [
				{ value: "Full Day", label: __("Full Day (00:00–24:00)") },
				{ value: "A", label: __("Shift A (06:00–14:00)") },
				{ value: "B", label: __("Shift B (14:00–22:00)") },
				{ value: "C", label: __("Shift C (22:00–06:00 next day)") },
			],
			default: "Full Day",
			reqd: 1,
		},
		{
			fieldname: "movement",
			label: __("Movement"),
			fieldtype: "Select",
			options: ["All", "Inward", "Outward"],
			default: "All",
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse / Store"),
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
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		// Section header rows: bold banner across the Voucher Type cell.
		if (data.row_type === "section") {
			if (column.fieldname === "voucher_type") {
				return "<span style='font-weight:700;font-size:13px;color:#1a3c5e'>" + (data.voucher_type || "") + "</span>";
			}
			return "";
		}
		// Subtotal rows
		if (data.row_type === "subtotal") {
			if (column.fieldname === "party") {
				return "<span style='font-weight:700;color:#1a3c5e'>" + (data.party || "") + "</span>";
			}
			if (column.fieldname === "in_qty" || column.fieldname === "out_qty") {
				return "<span style='font-weight:700'>" + value + "</span>";
			}
			if (column.fieldname === "balance_qty" || column.fieldname === "uom" ||
				column.fieldname === "voucher_type" || column.fieldname === "voucher_no" ||
				column.fieldname === "item_code" || column.fieldname === "item_name" ||
				column.fieldname === "warehouse" || column.fieldname === "posting_time") {
				return "";
			}
			return value;
		}
		// Data rows: colour the qty columns
		if (column.fieldname === "in_qty" && (parseFloat(data.in_qty) || 0) > 0) {
			value = "<span style='color:#2980b9'>" + value + "</span>";
		}
		if (column.fieldname === "out_qty" && (parseFloat(data.out_qty) || 0) > 0) {
			value = "<span style='color:#e67e22'>" + value + "</span>";
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
				if (!n) return "";
				return n.toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec });
			}
			function esc(s) {
				return (s || "").toString().replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
			}
			var sdate = frappe.query_report.get_filter_value("shift_date") || frappe.datetime.get_today();
			var sshift = frappe.query_report.get_filter_value("shift") || "Full Day";
			var heads = ["Time", "Voucher Type", "Voucher / GRN No", "Supplier / Department",
				"Item Code", "Item Description", "Warehouse", "Qty Received", "Qty Issued", "Balance In Stock", "UOM"];
			var html = '<html xmlns:o="urn:schemas-microsoft-com:office:office" '
				+ 'xmlns:x="urn:schemas-microsoft-com:office:excel" '
				+ 'xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="UTF-8">'
				+ '<!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet>'
				+ '<x:Name>Store Shift Report</x:Name><x:WorksheetOptions><x:DisplayGridlines/>'
				+ '</x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]-->'
				+ '</head><body><table border="0" style="font-family:Calibri;font-size:12pt;">'
				+ '<tr><td colspan="11" style="font-size:14pt;font-weight:bold;">STORES DAILY SHIFT REPORT</td></tr>'
				+ '<tr><td colspan="11">Date: ' + esc(sdate) + '&nbsp;&nbsp;&nbsp;Shift: ' + esc(sshift) + '</td></tr>'
				+ '<tr><td colspan="11"></td></tr></table>'
				+ '<table border="1" style="border-collapse:collapse;font-family:Calibri;font-size:11pt;">';
			html += '<tr style="background-color:#1a3c5e;color:#fff;font-weight:bold;">';
			heads.forEach(function (h, i) {
				html += '<td style="padding:6px 10px;' + (i >= 7 ? "text-align:right;" : "") + '">' + h + '</td>';
			});
			html += '</tr>';
			data.forEach(function (r) {
				if (r.row_type === "section") {
					html += '<tr style="background-color:#dce6f1;font-weight:bold;color:#1a3c5e;">'
						+ '<td colspan="11" style="padding:5px 8px;">' + esc(r.voucher_type) + '</td></tr>';
					return;
				}
				if (r.row_type === "subtotal") {
					html += '<tr style="background-color:#eaf2fb;font-weight:bold;">'
						+ '<td colspan="7" style="padding:4px 8px;text-align:right;">' + esc(r.party) + '</td>'
						+ '<td style="padding:4px 8px;text-align:right;">' + fnum(r.in_qty, 3) + '</td>'
						+ '<td style="padding:4px 8px;text-align:right;">' + fnum(r.out_qty, 3) + '</td>'
						+ '<td></td><td></td></tr>';
					return;
				}
				html += '<tr>'
					+ '<td style="padding:4px 8px;">' + esc(r.posting_time) + '</td>'
					+ '<td style="padding:4px 8px;">' + esc(r.voucher_type) + '</td>'
					+ '<td style="padding:4px 8px;">' + esc(r.voucher_no) + '</td>'
					+ '<td style="padding:4px 8px;">' + esc(r.party) + '</td>'
					+ '<td style="padding:4px 8px;">' + esc(r.item_code) + '</td>'
					+ '<td style="padding:4px 8px;">' + esc(r.item_name) + '</td>'
					+ '<td style="padding:4px 8px;">' + esc(r.warehouse) + '</td>'
					+ '<td style="padding:4px 8px;text-align:right;">' + fnum(r.in_qty, 3) + '</td>'
					+ '<td style="padding:4px 8px;text-align:right;">' + fnum(r.out_qty, 3) + '</td>'
					+ '<td style="padding:4px 8px;text-align:right;">' + fnum(r.balance_qty, 3) + '</td>'
					+ '<td style="padding:4px 8px;">' + esc(r.uom) + '</td></tr>';
			});
			html += '</table></body></html>';
			var blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8" });
			var url = URL.createObjectURL(blob);
			var a = document.createElement("a");
			a.href = url;
			a.download = "Store_Shift_Report_" + sdate + "_" + sshift + ".xls";
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		});
	},
};
