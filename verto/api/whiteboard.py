"""Personal and office whiteboards. Guest access is read-only and opt-in."""

import hmac
import json
import math
from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import get_url

BOARD_DOCTYPE = "Verto Whiteboard"
VISIBILITIES = {"Private", "Workspace", "Public link"}


def is_staff(user=None):
    user = user or frappe.session.user
    return user != "Guest" and (
        user == "Administrator" or frappe.db.get_value("User", user, "user_type") == "System User"
    )


def require_staff():
    if not is_staff():
        frappe.throw(_("Log in with a Desk account to access whiteboards."), frappe.PermissionError)


def can_edit(doc, user=None):
    user = user or frappe.session.user
    return is_staff(user) and (doc.owner == user or "System Manager" in frappe.get_roles(user))


def has_permission(doc, ptype=None, user=None, permission_type=None, **kwargs):
    ptype = ptype or permission_type or "read"
    user = user or frappe.session.user
    if not is_staff(user):
        return False
    if ptype == "create":
        return True
    if not doc:
        return False
    if can_edit(doc, user):
        return True
    return ptype in ("read", "select") and doc.visibility in {"Workspace", "Public link"}


def get_permission_query_conditions(user=None):
    user = user or frappe.session.user
    if not is_staff(user):
        return "1=0"
    if "System Manager" in frappe.get_roles(user):
        return ""
    return (
        f"(`tabVerto Whiteboard`.owner = {frappe.db.escape(user)} "
        "OR `tabVerto Whiteboard`.visibility IN ('Workspace', 'Public link'))"
    )


def parse_state(state):
    if isinstance(state, str):
        try:
            state = json.loads(state)
        except (ValueError, TypeError):
            frappe.throw(_("The whiteboard data is not valid JSON."))
    return state


def validate_state(state, allow_legacy=False):
    state = parse_state(state)
    if allow_legacy and isinstance(state, dict) and state.get("type") == "excalidraw":
        return state
    if not isinstance(state, dict) or state.get("type") != "verto-whiteboard" or state.get("version") != 1:
        frappe.throw(_("Unsupported whiteboard format. Your existing data has not been changed."))
    pages = state.get("pages")
    if not isinstance(pages, list) or not 1 <= len(pages) <= 100:
        frappe.throw(_("A whiteboard must have between 1 and 100 pages."))
    ids = set()
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("id"), str) or not page["id"] or len(page["id"]) > 100 or page["id"] in ids:
            frappe.throw(_("Whiteboard page identifiers must be unique."))
        ids.add(page["id"])
        if not isinstance(page.get("title"), str) or not page["title"].strip() or len(page["title"]) > 140:
            frappe.throw(_("Each page needs a name of up to 140 characters."))
        bounds = page.get("bounds")
        if not isinstance(bounds, dict) or any(
            not isinstance(bounds.get(k), (float, int)) or isinstance(bounds.get(k), bool)
            or not math.isfinite(bounds[k]) for k in ("x", "y", "width", "height")
        ) or bounds["width"] <= 0 or bounds["height"] <= 0:
            frappe.throw(_("Invalid page frame dimensions."))
        scene = page.get("scene")
        if not isinstance(scene, dict) or not isinstance(scene.get("elements"), list) or not isinstance(scene.get("appState"), dict) or not isinstance(scene.get("files"), dict):
            frappe.throw(_("Invalid whiteboard page content."))
        if any(not isinstance(element, dict) for element in scene["elements"]):
            frappe.throw(_("Invalid drawing element."))
    if state.get("activePageId") not in ids:
        frappe.throw(_("The selected whiteboard page does not exist."))
    return state


def check_revision(doc, revision):
    if str(revision) != str(doc.revision or 0):
        frappe.throw(
            _("This whiteboard changed in another session. Download your unsaved copy, then reload before editing."),
            frappe.TimestampMismatchError,
        )


def _personal(for_update=False):
    require_staff()
    name = frappe.session.user
    if frappe.db.exists("User Whiteboard State", name):
        return frappe.get_doc("User Whiteboard State", name, for_update=for_update)
    doc = frappe.new_doc("User Whiteboard State")
    doc.user = name
    doc.revision = 0
    return doc


def _board(name, for_update=False):
    if not isinstance(name, str) or not name:
        frappe.throw(_("Whiteboard not found."), frappe.DoesNotExistError)
    return frappe.get_doc(BOARD_DOCTYPE, name, for_update=for_update)


def _can_read(doc, token):
    if has_permission(doc, "read"):
        return True
    return (
        doc.visibility == "Public link" and isinstance(token, str) and bool(doc.public_token)
        and hmac.compare_digest(token.encode(), doc.public_token.encode())
    )


def _display_url(doc, public=False):
    url = get_url("/whiteboard-display?" + urlencode({"board": doc.name}))
    if public and doc.visibility == "Public link" and doc.public_token:
        url += "#" + urlencode({"token": doc.public_token})
    return url


def _snapshot(doc, personal=False, revision=None):
    editable = personal or can_edit(doc)
    result = {
        "name": "personal" if personal else doc.name,
        "title": _("My whiteboard") if personal else doc.title,
        "visibility": "Private" if personal else doc.visibility,
        "can_edit": editable,
        "revision": doc.revision or 0,
        "modified": str(doc.modified or ""),
    }
    if not personal and editable:
        result["display_url"] = _display_url(doc, public=True)
    if revision is not None and str(revision) == str(result["revision"]):
        result["not_modified"] = True
    else:
        result["state"] = parse_state(doc.state) if doc.state else None
    return result


def _no_cache():
    # Shared links can be revoked. Never let a browser/proxy cache their payloads.
    frappe.local.response_headers["Cache-Control"] = "no-store"


@frappe.whitelist(methods=["GET"])
def get_whiteboards():
    require_staff()
    return frappe.get_list(
        BOARD_DOCTYPE, fields=["name", "title", "visibility", "owner"],
        order_by="modified desc", limit_page_length=0,
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_whiteboard(name="personal", token=None, revision=None):
    _no_cache()
    if name == "personal":
        return _snapshot(_personal(), personal=True, revision=revision)
    doc = _board(name)
    if not _can_read(doc, token):
        frappe.throw(_("This whiteboard is private or its display link has been revoked."), frappe.PermissionError)
    return _snapshot(doc, revision=revision)


@frappe.whitelist(methods=["POST"])
def create_whiteboard(title, state):
    require_staff()
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 140:
        frappe.throw(_("Enter a board name of up to 140 characters."))
    doc = frappe.get_doc({
        "doctype": BOARD_DOCTYPE, "title": title.strip(), "visibility": "Workspace",
        "state": json.dumps(validate_state(state)),
    })
    doc.insert()
    return _snapshot(doc)


@frappe.whitelist(methods=["POST"])
def save_whiteboard(state, revision, name="personal"):
    require_staff()
    personal = name == "personal"
    doc = _personal(for_update=True) if personal else _board(name, for_update=True)
    if not personal and not can_edit(doc):
        frappe.throw(_("Only the board owner or a System Manager can edit this whiteboard."), frappe.PermissionError)
    check_revision(doc, revision)
    doc.state = json.dumps(validate_state(state))
    doc.save(ignore_permissions=personal)
    return {"saved": True, "revision": doc.revision, "modified": str(doc.modified)}


@frappe.whitelist(methods=["POST"])
def update_whiteboard_sharing(name, visibility, revision, title=None):
    require_staff()
    doc = _board(name, for_update=True)
    if not can_edit(doc):
        frappe.throw(_("Only the board owner or a System Manager can change sharing."), frappe.PermissionError)
    check_revision(doc, revision)
    if visibility not in VISIBILITIES:
        frappe.throw(_("Invalid sharing setting."))
    doc.visibility = visibility
    if title is not None:
        doc.title = title
    doc.save()
    return _snapshot(doc)


@frappe.whitelist(methods=["POST"])
def save_user_whiteboard_state(state: str):
    """Compatibility for cached clients; never let them overwrite a paged board."""
    doc = _personal(for_update=True)
    existing = parse_state(doc.state) if doc.state else None
    if isinstance(existing, dict) and existing.get("type") == "verto-whiteboard":
        frappe.throw(_("Reload Whiteboard to use pages. Your saved pages have not been changed."))
    doc.state = json.dumps(validate_state(state, allow_legacy=True))
    doc.save(ignore_permissions=True)
    return {"saved": True}
