frappe.query_reports["Creditors Summary - Split"] = {
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
            fieldname: "as_on_date",
            label: __("As On Date"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
    ],
    tree: true,
    name_field: "row_id",
    parent_field: "parent_id",
    initial_depth: 0,

    onload: function (report) {
        report.page.add_inner_button(__("Export to Excel"), function () {
            const data = frappe.query_report.data;
            if (!data || !data.length) {
                frappe.msgprint(__("No data to export."));
                return;
            }

            function formatCurrency(val) {
                var num = parseFloat(val) || 0;
                return num.toLocaleString("en-IN", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            }

            var html = '<html xmlns:o="urn:schemas-microsoft-com:office:office" '
                     + 'xmlns:x="urn:schemas-microsoft-com:office:excel" '
                     + 'xmlns="http://www.w3.org/TR/REC-html40">';
            html += '<head><meta charset="UTF-8">';
            html += '<!--[if gte mso 9]><xml><x:ExcelWorkbook><x:ExcelWorksheets>';
            html += '<x:ExcelWorksheet><x:Name>Creditors Summary</x:Name>';
            html += '<x:WorksheetOptions><x:DisplayGridlines/></x:WorksheetOptions>';
            html += '</x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml><![endif]-->';
            html += '</head><body>';
            html += '<table border="1" style="border-collapse:collapse;font-family:Calibri;font-size:11pt;">';

            // Header row
            var headers = ["Supplier","Opening","Purchase Invoice","Credit Note","Debit Note","Paid","Outstanding"];
            html += '<tr style="background-color:#5e1a1a;">';
            headers.forEach(function (h, i) {
                var align = i === 0 ? "left" : "right";
                var w = i === 0 ? "300pt" : "100pt";
                html += '<td style="font-weight:bold;color:#ffffff;padding:6px 10px;width:' + w + ';text-align:' + align + ';">' + h + '</td>';
            });
            html += '</tr>';

            data.forEach(function (row) {
                var isGroup  = !row.party_id;
                var indent   = row.indent || 0;
                var padding  = (indent * 20) + "px";
                var label    = (row.label || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

                var outstanding = parseFloat(row.outstanding) || 0;
                var osColor = outstanding > 0 ? "#c0392b" : outstanding < 0 ? "#27ae60" : "#000000";
                var cells = [
                    {v: row.opening,          c: "#7f8c8d"},
                    {v: row.purchase_invoice, c: "#c0392b"},
                    {v: row.credit_note,      c: "#8e44ad"},
                    {v: row.debit_note,       c: "#2980b9"},
                    {v: row.paid,             c: "#27ae60"},
                    {v: row.outstanding,      c: osColor},
                ];

                if (isGroup) {
                    var bgColor  = indent === 0 ? "#f1dcdc" : "#fbeaea";
                    var fontSize = indent === 0 ? "11pt" : "10.5pt";
                    html += '<tr style="background-color:' + bgColor + ';">';
                    html += '<td style="font-weight:bold;font-size:' + fontSize + ';padding:5px 8px;padding-left:' + padding + ';color:#5e1a1a;">' + label + '</td>';
                    cells.forEach(function (cell) {
                        html += '<td style="font-weight:bold;font-size:' + fontSize + ';padding:5px 8px;text-align:right;color:' + cell.c + ';">' + formatCurrency(cell.v) + '</td>';
                    });
                    html += '</tr>';
                } else {
                    html += '<tr>';
                    html += '<td style="padding:4px 8px;padding-left:' + padding + ';color:#333333;">' + label + '</td>';
                    cells.forEach(function (cell) {
                        html += '<td style="padding:4px 8px;text-align:right;color:' + cell.c + ';">' + formatCurrency(cell.v) + '</td>';
                    });
                    html += '</tr>';
                }
            });

            html += '</table></body></html>';

            var blob = new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8" });
            var url  = URL.createObjectURL(blob);
            var a    = document.createElement("a");
            var as_on = frappe.query_report.get_filter_value("as_on_date") || frappe.datetime.get_today();
            a.href     = url;
            a.download = "Creditors_Summary_Split_" + as_on + ".xls";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
    },

    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;
        var company    = frappe.query_report.get_filter_value("company")    || "";
        var as_on_date = frappe.query_report.get_filter_value("as_on_date") || "";
        var from_date  = frappe.query_report.get_filter_value("from_date")  || "";
        if (column.fieldname === "label") {
            if (!data.party_id) {
                var indent = data.indent || 0;
                if (indent === 0) {
                    value = "<span style='font-weight:700;font-size:13px;color:#5e1a1a'>"
                        + (data.label || "") + "</span>";
                } else {
                    value = "<span style='font-weight:600;font-size:12px;color:#822c2c'>"
                        + (data.label || "") + "</span>";
                }
            } else {
                var url = "/app/query-report/General Ledger"
                    + "?company="    + encodeURIComponent(company)
                    + "&from_date="  + encodeURIComponent(from_date)
                    + "&to_date="    + encodeURIComponent(as_on_date)
                    + "&party_type=" + encodeURIComponent("Supplier")
                    + "&party="      + encodeURIComponent(data.party_id);
                value = "<a href='" + url + "' style='color:#1a73e8;font-weight:500'>"
                    + (data.label || "")
                    + " <span style='font-size:10px;opacity:0.7'>↗</span></a>";
            }
        }
        if (column.fieldname === "opening" && value) {
            value = "<span style='color:#7f8c8d;font-weight:500'>" + value + "</span>";
        }
        if (column.fieldname === "purchase_invoice" && value) {
            value = "<span style='color:#c0392b;font-weight:500'>" + value + "</span>";
        }
        if (column.fieldname === "credit_note" && value) {
            value = "<span style='color:#8e44ad;font-weight:500'>" + value + "</span>";
        }
        if (column.fieldname === "debit_note" && value) {
            value = "<span style='color:#2980b9;font-weight:500'>" + value + "</span>";
        }
        if (column.fieldname === "paid" && value) {
            value = "<span style='color:#27ae60;font-weight:500'>" + value + "</span>";
        }
        if (column.fieldname === "outstanding") {
            var amt = parseFloat(data.outstanding) || 0;
            var display = value || frappe.format(amt, {fieldtype: "Currency"});
            if (amt > 0) {
                value = "<span style='color:#c0392b;font-weight:700'>" + display + "</span>";
            } else if (amt < 0) {
                value = "<span style='color:#27ae60;font-weight:700'>" + display + "</span>";
            }
        }
        return value;
    },
};
