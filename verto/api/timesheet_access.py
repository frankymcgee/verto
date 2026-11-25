"""Shared navigation capability for the authenticated timesheet review tools."""

import frappe

APPROVER_ROLES = {"System Manager", "Accounts Manager", "HR Manager", "Projects Manager", "Verto Planner Manager"}


def can_review_timesheets():
    user = frappe.session.user
    return bool(user and user != "Guest"
                and (user == "Administrator" or APPROVER_ROLES.intersection(frappe.get_roles(user)))
                and frappe.has_permission("Timesheet", "read"))
