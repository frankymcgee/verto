"""Shared requests used by the mobile and Desk project-analysis shortcuts."""

import json

import frappe


@frappe.whitelist()
def get_project_dashboard_prompt(project):
    if frappe.session.user == "Guest":
        frappe.throw("Sign in to use PERI dashboard analysis.", frappe.PermissionError)
    return build_project_dashboard_prompt(project)


def build_project_dashboard_prompt(project):
    if not isinstance(project, str) or not project.strip():
        frappe.throw("A project is required for dashboard analysis.")
    reference = json.dumps(project.strip(), ensure_ascii=False)
    return (
        f'Analyse the "Shutdown Safety Metrics" Insights dashboard for project {reference}. '
        "Apply the dashboard's relevant project filters to that exact project before reading the charts. "
        "Verify which charts receive the project filters and clearly flag any that do not. "
        "Cover every chart with actual figures, units, supported comparisons and practical safety improvements. "
        "State the active filters, reporting period and any missing or limited data. "
        "Do not substitute another dashboard or present unfiltered figures as project-specific."
    )
