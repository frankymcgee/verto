"""Small, transaction-safe invalidations for authenticated planner viewers."""
import frappe

EVENT = "verto:planner_changed"
ROOM = "verto:planner"

DOCTYPE_SCOPES = {
    "Shift Assignment": ("roster",),
    "Shift Schedule Assignment": ("roster",),
    "Shift Schedule": ("roster",),
    "Shift Type": ("roster",),
    "Shift Location": ("roster",),
    "Leave Application": ("roster",),
    "Leave Type": ("roster",),
    "Holiday List": ("roster",),
    "Event": ("roster",),
    "Daily Timesheet": ("roster",),
    "Project": ("projects",),
    "Task": ("projects",),
    "ToDo": ("projects",),
    "Customer": ("projects",),
    "Employee": ("employees", "roster"),
    "Department": ("employees",),
    "Designation": ("employees",),
    "Branch": ("employees",),
    "Company": ("employees", "projects", "roster"),
    "Verto Mobile Settings": ("settings", "roster"),
}


@frappe.whitelist(methods=["GET"])
def can_subscribe():
    if not frappe.session.user or frappe.session.user == "Guest":
        return False
    from verto.access import can_view_planner_app

    # Retain access for existing Employee readers as well as Verto app roles.
    return bool(can_view_planner_app() or frappe.has_permission("Employee", ptype="read"))


def publish_scope(scope):
    if scope not in {"roster", "projects", "employees", "settings"}:
        raise ValueError("Unknown planner refresh scope")
    # No names, user IDs, dates or document contents are broadcast. Frappe
    # deduplicates equal (event, message, room) entries within a transaction and
    # drops its after-commit log on rollback, including bulk roster operations.
    frappe.publish_realtime(EVENT, {"scope": scope}, room=ROOM, after_commit=True)


def document_changed(doc, method=None, *args, **kwargs):
    if doc.doctype == "ToDo" and doc.get("reference_type") != "Task":
        return
    for scope in DOCTYPE_SCOPES.get(doc.doctype, ()):
        publish_scope(scope)
