import frappe
from frappe.utils import add_days, now_datetime


DOCTYPE = "Verto Mobile Notification"


def _recipient_filters():
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)
    return {"recipient": user}


@frappe.whitelist(methods=["GET"])
def list_notifications():
    filters = _recipient_filters()
    frappe.local.response_headers["Cache-Control"] = "no-store"
    return {
        "items": frappe.get_all(
            DOCTYPE,
            filters=filters,
            fields=["name", "title", "body", "target_url", "creation", "is_read"],
            order_by="creation desc, name desc",
            limit_page_length=50,
        ),
    }


@frappe.whitelist(methods=["POST"])
def mark_read(through: str):
    filters = _recipient_filters()
    if not isinstance(through, str) or not through:
        return
    creation = frappe.db.get_value(DOCTYPE, {**filters, "name": through}, "creation")
    if creation is None:
        return
    filters.update({"is_read": 0, "creation": ["<=", creation]})
    frappe.db.set_value(DOCTYPE, filters, "is_read", 1, update_modified=False)


def record_deliveries(recipients, payload):
    for recipient in recipients:
        frappe.get_doc({
            "doctype": DOCTYPE,
            "recipient": recipient,
            "title": str(payload.get("title") or "Verto")[:250],
            "body": str(payload.get("body") or "A new update is available.")[:2000],
            "target_url": str(payload.get("url") or "")[:2000],
        }).insert(ignore_permissions=True)


def delete_expired_notifications():
    frappe.db.delete(DOCTYPE, {"creation": ["<", add_days(now_datetime(), -90)]})
