// Copyright (c) 2026, Webwire and contributors
// For license information, please see license.txt

frappe.query_reports["Qualifications Matrix"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
		},
		{
			fieldname: "designation",
			label: __("Designation"),
			fieldtype: "Link",
			options: "Designation",
		},
		{
			fieldname: "employee_status",
			label: __("Employee Status"),
			fieldtype: "Select",
			options: ["", "Active", "Inactive", "Suspended", "Left"],
			default: "Active",
		},
		{
			fieldname: "qualification_category",
			label: __("Qualification Category"),
			fieldtype: "Select",
			options: [
				"",
				"Licence",
				"Certification",
				"Competency",
				"Site Induction",
				"Client Qualification",
				"Medical / Fitness",
				"Training",
				"Other",
			],
		},
		{
			fieldname: "qualification_scope",
			label: __("Show"),
			fieldtype: "Select",
			options: ["Required and Recorded", "All Qualifications"],
			default: "Required and Recorded",
		},
		{
			fieldname: "compliance_status",
			label: __("Overall Status"),
			fieldtype: "Select",
			options: ["", "Compliant", "Attention Required", "Non-compliant", "No Requirements"],
		},
	],

	formatter(value, row, column, data, default_formatter) {
		if (column.fieldname === "compliance_status") {
			return qualification_matrix_status_badge(value, qualification_matrix_overall_colours[value]);
		}

		if (!column.fieldname.startsWith("qualification_")) {
			return default_formatter(value, row, column, data);
		}

		if (!value) {
			return '<span style="color: var(--text-muted);">—</span>';
		}

		const details = data[`${column.fieldname}__details`] || column.label;
		const href = `/app/employee/${encodeURIComponent(data.employee)}`;
		return `<a href="${href}" title="${qualification_matrix_escape_html(details)}" style="text-decoration: none;">${qualification_matrix_status_badge(value, qualification_matrix_status_colours[value])}</a>`;
	},
};

var qualification_matrix_status_colours = {
	Valid: ["#e8f7ee", "#16794b"],
	"Expiring Soon": ["#fff4d6", "#946c00"],
	Expired: ["#fde8e8", "#b42318"],
	Missing: ["#f2f4f7", "#475467"],
	Rejected: ["#fde8e8", "#b42318"],
	"Pending Verification": ["#e8f1ff", "#175cd3"],
	Incomplete: ["#fff4d6", "#946c00"],
};

var qualification_matrix_overall_colours = {
	Compliant: ["#e8f7ee", "#16794b"],
	"Attention Required": ["#fff4d6", "#946c00"],
	"Non-compliant": ["#fde8e8", "#b42318"],
	"No Requirements": ["#f2f4f7", "#475467"],
};

function qualification_matrix_status_badge(value, colours) {
	const [background, colour] = colours || ["#f2f4f7", "#475467"];
	return `<span style="display: inline-block; padding: 2px 8px; border-radius: 999px; background: ${background}; color: ${colour}; font-size: 11px; font-weight: 600; white-space: nowrap;">${qualification_matrix_escape_html(value || "")}</span>`;
}

function qualification_matrix_escape_html(value) {
	const element = document.createElement("div");
	element.textContent = String(value ?? "");
	return element.innerHTML;
}
