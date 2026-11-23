"""Open native Flow inside Ask PERI, using the caller's existing permissions."""

from urllib.parse import quote

import frappe
from frappe.utils import cint

from verto.api.mobile.boot import get_mobile_settings, get_setting, require_login


def validate_flow_settings(settings):
    if not all(frappe.db.exists("DocType", dt) for dt in ("Flow Session", "Flow Agent")):
        frappe.throw("Flow is not installed on this site. Update Frappe and configure Flow first.")

    agent = str(get_setting(settings, "peri_flow_agent", "PERI")).strip()
    if not frappe.db.exists("Flow Agent", agent):
        frappe.throw(f"Flow agent {agent} does not exist. Enter the exact agent ID in Verto Mobile Settings.")
    if not cint(frappe.db.get_value("Flow Agent", agent, "enabled")):
        frappe.throw(f"Flow agent {agent} is disabled.")
    return agent


@frappe.whitelist(methods=["POST"])
def open_peri_chat(session=None, new_chat=0):
    require_login()
    settings = get_mobile_settings()
    if get_setting(settings, "peri_chat_version", "Raven") != "Flow":
        frappe.throw("Select Flow as the Ask PERI Version in Verto Mobile Settings first.")

    agent = validate_flow_settings(settings)
    frappe.has_permission("Flow Session", "read", throw=True)
    frappe.has_permission("Flow Agent", "read", agent, throw=True)

    name = None
    if not cint(new_chat):
        # A browser remembers its selected conversation, scoped to the signed-in user.
        # Never accept a shared or another user's session as that user's PERI chat.
        if session and frappe.db.exists("Flow Session", session):
            doc = frappe.get_doc("Flow Session", session)
            if doc.owner != frappe.session.user:
                frappe.throw("This PERI conversation belongs to another user.", frappe.PermissionError)
            frappe.has_permission("Flow Session", "read", doc, throw=True)
            if doc.agent == agent and doc.source == "Manual":
                name = doc.name

        if not name:
            rows = frappe.get_list(
                "Flow Session",
                filters={"owner": frappe.session.user, "agent": agent, "source": "Manual"},
                fields=["name"],
                order_by="modified desc",
                limit_page_length=1,
            )
            if rows:
                name = rows[0]["name"]

    if not name:
        # Import only in Flow mode, so older Frappe installations can still use Raven.
        # Native Flow enforces create, agent and model permissions and normal approvals.
        from frappe.flow.api import create_session

        name = create_session(agent=agent)["name"]

    return {"url": f"/flow/s/{quote(name, safe='')}", "session": name, "agent": agent}
