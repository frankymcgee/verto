"""Permission-filtered investigations, evidence, analysis and human approvals."""

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, now_datetime, today

from verto.safety.investigation_rules import (
    CONTROL_TYPES, EDITABLE_STATUSES, ICAM_CATEGORIES, METHODS,
    ROW_TABLES, STATUSES, closure_readiness, review_readiness, text, validate_structure,
)

DOCTYPE = "Verto Investigation"
INVESTIGATOR = "Verto Investigator"
MANAGER = "Verto Investigation Manager"
MANAGERS = frozenset((MANAGER, "System Manager"))
SOURCES = ("EHS Incident", "Shutdown Incident Tracker")
PARENT_FIELDS = (
    "title", "method", "incident_datetime", "incident_time_precision", "due_date", "project", "site_location", "incident_type",
    "classification", "actual_severity", "potential_severity", "source_doctype", "source_name",
    "external_reference", "description", "immediate_response", "regulatory_review", "reportability_notes",
    "regulator", "regulator_reference", "lead_investigator", "reviewer", "findings_summary", "lessons_learned",
)
CHILD_FIELDS = {
    "team": ("user", "team_role"),
    "evidence": ("entry_id", "title", "evidence_type", "observed_at", "notes", "file", "verification_status", "verification_notes"),
    "timeline": ("entry_id", "event_datetime", "description", "evidence_refs"),
    "five_whys": ("entry_id", "parent_id", "description", "finding_status", "evidence_refs", "is_root_cause", "root_cause_reason"),
    "icam_factors": ("entry_id", "category", "description", "finding_status", "evidence_refs", "contributes_to"),
    "category_reviews": ("category", "no_finding_reason"),
    "actions": ("entry_id", "title", "details", "finding_refs", "assigned_to_user", "due_date", "priority", "control_type", "success_criteria", "verifier", "verification_due_date"),
}
ACTION_PROTECTED = ("action_status", "completion_notes", "completion_file", "completed_by", "completed_on", "verification_notes", "verified_by", "verified_on", "cancellation_reason")
PARENT_PROTECTED = ("status", "review_notes", "approved_by", "approved_on", "closure_summary", "closed_by", "closed_on")


def is_manager(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or bool(MANAGERS.intersection(frappe.get_roles(user)))


def can_access(user=None):
    user = user or frappe.session.user
    return bool(user and user != "Guest" and (is_manager(user) or INVESTIGATOR in frappe.get_roles(user)))


def _require_access():
    if not can_access():
        frappe.throw(_("You do not have access to Verto Investigations."), frappe.PermissionError)


def has_permission(doc, user=None, ptype=None, permission_type=None, **kwargs):
    user = user or frappe.session.user
    kind = ptype or permission_type or "read"
    if not can_access(user) or kind in ("delete", "cancel", "submit", "amend", "share", "email", "export"):
        return False
    if is_manager(user) or kind == "create" or doc is None:
        return True
    if doc.get("lead_investigator") == user or doc.get("reviewer") == user:
        return True
    return any(row.get("user") == user and (kind not in ("write", "submit") or row.get("team_role") != "Observer") for row in doc.get("team") or [])


def query_conditions(user=None):
    user = user or frappe.session.user
    if not can_access(user):
        return "1=0"
    if is_manager(user):
        return ""
    escaped = frappe.db.escape(user)
    return (f"(`tab{DOCTYPE}`.lead_investigator = {escaped} OR `tab{DOCTYPE}`.reviewer = {escaped} "
            f"OR EXISTS (SELECT 1 FROM `tabInvestigation Team Member` member "
            f"WHERE member.parent = `tab{DOCTYPE}`.name AND member.parenttype = '{DOCTYPE}' "
            f"AND member.parentfield = 'team' AND member.user = {escaped}))")


@contextmanager
def _mutation(kind):
    previous = frappe.flags.get("verto_investigation_mutation")
    frappe.flags.verto_investigation_mutation = kind
    try:
        yield
    finally:
        frappe.flags.verto_investigation_mutation = previous


def _snapshot(rows, fields):
    return [{field: str(row.get(field) or "") for field in fields} for row in rows or []]


def _check_file(url, investigation):
    if not url:
        return
    files = frappe.get_all("File", filters={"file_url": url, "is_private": 1,
        "attached_to_doctype": DOCTYPE, "attached_to_name": investigation}, pluck="name", limit_page_length=1)
    if not files or not str(url).startswith("/private/files/"):
        frappe.throw(_("Evidence files must be private attachments to this investigation."))
    frappe.get_doc("File", files[0]).check_permission("read")


def _eligible_user(user, reviewer=False):
    if not user:
        return
    record = frappe.db.get_value("User", user, ["enabled", "user_type"], as_dict=True)
    if not record or not record.enabled or record.user_type != "System User" or not (is_manager(user) if reviewer else can_access(user)):
        frappe.throw(_("Choose an enabled investigation user{0}.").format(_(" with manager access") if reviewer else ""))


def validate_document(doc):
    """Enforce the same boundaries on Desk, REST, imports and this app."""
    old = doc.get_doc_before_save() if not doc.is_new() else None
    mutation = frappe.flags.get("verto_investigation_mutation")
    if doc.method not in METHODS or doc.status not in STATUSES:
        frappe.throw(_("Choose a valid investigation method and status."))
    if doc.incident_time_precision not in ("Exact", "Approximate", "Date only"):
        frappe.throw(_("Record whether the incident time is exact, approximate or date only."))
    if not old:
        if doc.status != "Draft" or any(doc.get(field) for field in PARENT_PROTECTED if field != "status") or doc.get("history"):
            frappe.throw(_("New investigations must start as drafts without approval history."))
        if not is_manager() and doc.lead_investigator != frappe.session.user:
            frappe.throw(_("Create the draft under your own lead investigator account."), frappe.PermissionError)
    elif not mutation:
        if old.status not in EDITABLE_STATUSES:
            frappe.throw(_("This investigation is locked for review or action follow-up. Use its workflow controls."))
        if any(str(doc.get(key) or "") != str(old.get(key) or "") for key in PARENT_PROTECTED):
            frappe.throw(_("Use the investigation workflow to change approval or close-out details."), frappe.PermissionError)
        if _snapshot(doc.get("history"), ("event", "actor", "recorded_at", "notes")) != _snapshot(old.get("history"), ("event", "actor", "recorded_at", "notes")):
            frappe.throw(_("Investigation history must be retained."), frappe.PermissionError)

    if doc.reviewer and doc.reviewer == doc.lead_investigator:
        frappe.throw(_("The reviewer must be different from the lead investigator."))
    # Historic personnel stay in the record after account deactivation. Check
    # eligibility when assigning people, and again before approving new work.
    if not old or old.lead_investigator != doc.lead_investigator:
        _eligible_user(doc.lead_investigator)
    if not old or old.reviewer != doc.reviewer:
        _eligible_user(doc.reviewer, reviewer=True)
    old_team = {row.user: row.team_role for row in old.get("team") or []} if old else {}
    members = {doc.lead_investigator, doc.reviewer} - {None, ""}
    contributors = set(members)
    for row in doc.get("team") or []:
        if old_team.get(row.user) != row.team_role:
            _eligible_user(row.user)
        if row.user in members:
            frappe.throw(_("List each team member once; the lead and reviewer already have access."))
        if row.team_role not in ("Investigator", "Subject matter expert", "Observer"):
            frappe.throw(_("Choose a valid investigation team role."))
        members.add(row.user)
        if row.team_role != "Observer":
            contributors.add(row.user)
    if doc.project and (not old or old.project != doc.project):
        frappe.get_doc("Project", doc.project).check_permission("read")
    if bool(doc.source_doctype) != bool(doc.source_name):
        frappe.throw(_("Select both the source incident type and record, or leave both empty."))
    if doc.source_doctype and (not old or (old.source_doctype, old.source_name) != (doc.source_doctype, doc.source_name)):
        if doc.source_doctype not in SOURCES:
            frappe.throw(_("Unsupported incident source."))
        frappe.get_doc(doc.source_doctype, doc.source_name).check_permission("read")

    for table, prefix in ROW_TABLES.items():
        if len(doc.get(table) or []) > 200:
            frappe.throw(_("Use no more than 200 entries per investigation section."))
        for row in doc.get(table) or []:
            row.entry_id = row.get("entry_id") or f"{prefix}-{frappe.generate_hash(length=12)}"
    old_evidence = {row.entry_id: row for row in old.get("evidence") or []} if old else {}
    for row in doc.get("evidence") or []:
        previous = old_evidence.get(row.entry_id)
        row.recorded_by = previous.recorded_by if previous else frappe.session.user
        changed = previous and any(str(row.get(field) or "") != str(previous.get(field) or "") for field in ("title", "notes", "file", "observed_at", "evidence_type"))
        if previous and previous.verification_status == "Verified" and changed:
            row.verification_status = "Unverified"
        if row.verification_status not in ("Unverified", "Verified", "Disputed"):
            frappe.throw(_("Choose a valid evidence status."))
        if row.verification_status == "Verified":
            if not text(row.verification_notes) or not (text(row.notes) or row.file):
                frappe.throw(_("Record the evidence and verification basis before marking it verified."))
            if not previous or previous.verification_status != "Verified" or row.verification_notes != previous.verification_notes:
                row.verified_by, row.verified_on = frappe.session.user, now_datetime()
            else:
                row.verified_by, row.verified_on = previous.verified_by, previous.verified_on
        else:
            row.verified_by = row.verified_on = None
        _check_file(row.file, doc.name)

    categories = [row.category for row in doc.get("category_reviews") or []]
    if len(categories) != len(set(categories)) or any(category not in ICAM_CATEGORIES for category in categories):
        frappe.throw(_("Review each ICAM category once."))
    for category in ICAM_CATEGORIES:
        if category not in categories:
            doc.append("category_reviews", {"category": category})
    old_actions = {row.entry_id: row for row in old.get("actions") or []} if old else {}
    current_actions = {row.entry_id: row for row in doc.get("actions") or []}
    if old and old.method != doc.method and any(row.action_status != "Open" for row in old_actions.values()) and doc.method != "5 Whys + ICAM":
        frappe.throw(_("Retain analysis behind progressed actions. Choose 5 Whys + ICAM when adding another method."))
    for key, previous in old_actions.items():
        if previous.action_status != "Open" and key not in current_actions:
            frappe.throw(_("Retain actions with progress or completion history; cancel them with a reason instead."))
    for row in doc.get("actions") or []:
        previous = old_actions.get(row.entry_id)
        if not previous:
            if any(row.get(field) for field in ACTION_PROTECTED if field != "action_status") or row.action_status not in (None, "", "Open"):
                frappe.throw(_("New actions must start open without completion or verification details."))
            row.action_status = "Open"
        elif mutation != "action":
            if any(str(row.get(field) or "") != str(previous.get(field) or "") for field in ACTION_PROTECTED):
                frappe.throw(_("Use the action workflow to record progress, completion and verification."), frappe.PermissionError)
            if previous.action_status != "Open" and _snapshot([row], CHILD_FIELDS["actions"]) != _snapshot([previous], CHILD_FIELDS["actions"]):
                frappe.throw(_("Retain the details of actions with progress history; add a replacement action after reopening."))
        if row.control_type and row.control_type not in CONTROL_TYPES:
            frappe.throw(_("Choose a valid hierarchy-of-control category."))
        for field in ("assigned_to_user", "verifier"):
            user = row.get(field)
            if user and user not in contributors and (not previous or previous.get(field) != user):
                frappe.throw(_("Add action owners and verifiers to the investigation team before assigning them."))
        if row.assigned_to_user and row.assigned_to_user == row.verifier:
            frappe.throw(_("Assign an independent action verifier."))
        if row.due_date and row.verification_due_date and getdate(row.verification_due_date) < getdate(row.due_date):
            frappe.throw(_("The effectiveness review date cannot be before the action due date."))
        _check_file(row.completion_file, doc.name)
    errors = validate_structure(doc.as_dict())
    if errors:
        frappe.throw("\n".join(errors))
    doc.open_actions = sum(row.action_status not in ("Verified", "Cancelled") for row in doc.get("actions") or [])


def validate_attachment(file, method=None):
    old = file.get_doc_before_save() if not file.is_new() else None
    if old and old.get("attached_to_doctype") == DOCTYPE and (file.get("attached_to_doctype"), file.get("attached_to_name")) != (old.get("attached_to_doctype"), old.get("attached_to_name")):
        frappe.throw(_("Investigation evidence attachments must remain linked to their investigation."))
    if file.get("attached_to_doctype") != DOCTYPE:
        return
    if file.get("is_private") not in (True, 1, "1"):
        frappe.throw(_("Investigation attachments must remain private."))
    doc = _get(file.get("attached_to_name"))
    doc.check_permission("write")
    if doc.status not in EDITABLE_STATUSES | {"Actions in Progress"}:
        frappe.throw(_("Attachments cannot be changed during review or after close-out."))


def retain_attachment(file, method=None):
    if file.get("attached_to_doctype") == DOCTYPE and not frappe.flags.in_uninstall:
        frappe.throw(_("Investigation evidence attachments must be retained."), frappe.PermissionError)


class InvestigationFileMixin:
    def before_insert(self):
        # File.before_insert writes bytes before its validate method runs.
        validate_attachment(self)
        return super().before_insert()

    def on_trash(self):
        # Check before File.on_trash can remove the underlying bytes.
        retain_attachment(self)
        return super().on_trash()


def _get(name, modified=None, lock=False):
    _require_access()
    doc = frappe.get_doc(DOCTYPE, name)
    doc.check_permission("write" if lock else "read")
    if lock:
        frappe.db.sql("SELECT name FROM `tabVerto Investigation` WHERE name=%s FOR UPDATE", (name,))
        doc.reload()
        doc.check_permission("write")
        if not modified or get_datetime(doc.modified) != get_datetime(modified):
            frappe.throw(_("This investigation changed. Reload it before saving your changes."), frappe.TimestampMismatchError)
    return doc


def _history(doc, event, notes=""):
    doc.append("history", {"event": event, "actor": frappe.session.user, "recorded_at": now_datetime(), "notes": text(notes)})


def _payload(doc):
    user = frappe.session.user
    writable = bool(doc.has_permission("write"))
    manager = is_manager()
    result = doc.as_dict()
    result["capabilities"] = {
        "can_edit": writable and doc.status in EDITABLE_STATUSES,
        "can_review": writable and manager and user == doc.reviewer and user != doc.lead_investigator and doc.status == "In Review",
        "can_withdraw": writable and (manager or user == doc.lead_investigator) and doc.status == "In Review",
        "can_close": writable and manager and doc.status == "Actions in Progress",
        "can_reopen": writable and manager and doc.status in ("Closed", "Actions in Progress"),
        "can_upload": writable and doc.status in EDITABLE_STATUSES | {"Actions in Progress"},
    }
    result["readiness"] = review_readiness(result)
    result["closure_readiness"] = closure_readiness(result)
    for action in result.get("actions") or []:
        active = writable and doc.status == "Actions in Progress"
        action["can_complete"] = active and user != action.get("verifier") and (user == action.get("assigned_to_user") or manager) and action.get("action_status") in ("Open", "In Progress")
        action["can_verify"] = active and user == action.get("verifier") and user not in (action.get("assigned_to_user"), action.get("completed_by")) and action.get("action_status") == "Completed"
        action["can_cancel"] = active and manager and action.get("action_status") not in ("Verified", "Cancelled")
        action["can_reassign"] = writable and manager and doc.status in ("Actions in Progress", "Reopened") and action.get("action_status") not in ("Verified", "Cancelled")
    return result


@frappe.whitelist()
def get_bootstrap():
    _require_access()
    from verto.default_apps import get_apps
    return {"user": frappe.session.user, "full_name": frappe.db.get_value("User", frappe.session.user, "full_name"),
        "is_manager": is_manager(), "methods": METHODS, "statuses": STATUSES,
        "icam_categories": ICAM_CATEGORIES, "control_types": CONTROL_TYPES, "apps": get_apps()}


@frappe.whitelist()
def list_investigations(search="", status="", method="", start=0, page_length=25):
    _require_access()
    start, page_length = max(0, min(int(start or 0), 100000)), max(1, min(int(page_length or 25), 100))
    filters = {}
    if status in STATUSES:
        filters["status"] = status
    if method in METHODS:
        filters["method"] = method
    or_filters = {key: ["like", "%" + text(search)[:100] + "%"] for key in ("title", "name", "external_reference")} if search else None
    rows = frappe.get_list(DOCTYPE, filters=filters, or_filters=or_filters,
        fields=["name", "title", "status", "method", "incident_datetime", "site_location", "project", "due_date", "lead_investigator", "potential_severity", "open_actions", "modified"],
        order_by="modified desc", start=start, page_length=page_length + 1)
    groups = frappe.get_list(DOCTYPE, fields=["status", {"COUNT": "name", "as": "total"}], group_by="status", limit=0)
    return {"items": rows[:page_length], "has_more": len(rows) > page_length,
        "counts": {row.status: row.total for row in groups}, "today": today()}


@frappe.whitelist()
def get_investigation(name):
    return _payload(_get(name))


@frappe.whitelist(methods=["POST"])
def save_investigation(data, expected_modified=None):
    _require_access()
    data = frappe.parse_json(data) if isinstance(data, str) else data
    if not isinstance(data, dict):
        frappe.throw(_("Supply an investigation record."))
    if data.get("name"):
        doc = _get(data["name"], expected_modified, lock=True)
    else:
        doc = frappe.new_doc(DOCTYPE)
        doc.check_permission("create")
        doc.lead_investigator = frappe.session.user
    for field in PARENT_FIELDS:
        if field in data:
            doc.set(field, data[field])
    for table, fields in CHILD_FIELDS.items():
        if table not in data:
            continue
        entries = data[table]
        if not isinstance(entries, list) or len(entries) > 200 or any(not isinstance(row, dict) for row in entries):
            frappe.throw(_("Invalid investigation entries."))
        existing = {row.get("entry_id") or row.get("user") or row.get("category"): row.as_dict() for row in doc.get(table) or []}
        clean = []
        for entry in entries:
            key = entry.get("entry_id") or entry.get("user") or entry.get("category")
            item = dict(existing.get(key) or {})
            item.update({field: entry.get(field) for field in fields})
            clean.append(item)
        doc.set(table, clean)
    doc.save()
    return _payload(doc)


@frappe.whitelist(methods=["POST"])
def transition(name, action, expected_modified, notes=""):
    doc = _get(name, expected_modified, lock=True)
    current = doc.status
    notes = text(notes)
    if action == "gather_evidence" and current in ("Draft", "Reopened"):
        doc.status = "Evidence Gathering"
    elif action == "analyse" and current in ("Draft", "Evidence Gathering", "Reopened"):
        doc.status = "Analysis"
    elif action == "submit_review" and current in EDITABLE_STATUSES:
        _check_review_people(doc)
        errors = review_readiness(doc.as_dict())
        if errors:
            frappe.throw("\n".join(errors))
        doc.status = "In Review"
    elif action == "withdraw_review" and current == "In Review" and (is_manager() or doc.lead_investigator == frappe.session.user):
        if not notes:
            frappe.throw(_("Record why the investigation is being withdrawn from review."))
        doc.status = "Analysis"
    elif action in ("approve", "return") and current == "In Review":
        if not is_manager() or doc.reviewer != frappe.session.user or doc.lead_investigator == frappe.session.user:
            frappe.throw(_("Only the appointed independent reviewer can record this decision."), frappe.PermissionError)
        if not notes:
            frappe.throw(_("Record the review decision and its reasons."))
        doc.review_notes = notes
        if action == "approve":
            _check_review_people(doc)
            errors = review_readiness(doc.as_dict())
            if errors:
                frappe.throw("\n".join(errors))
            doc.status, doc.approved_by, doc.approved_on = "Actions in Progress", frappe.session.user, now_datetime()
        else:
            doc.status = "Analysis"
    elif action == "close" and current == "Actions in Progress" and is_manager():
        errors = closure_readiness(doc.as_dict())
        if errors:
            frappe.throw("\n".join(errors))
        if not notes:
            frappe.throw(_("Record a close-out summary."))
        doc.status, doc.closure_summary, doc.closed_by, doc.closed_on = "Closed", notes, frappe.session.user, now_datetime()
    elif action == "reopen" and current in ("Closed", "Actions in Progress") and is_manager():
        if not notes:
            frappe.throw(_("Record why the investigation is being reopened."))
        doc.status = "Reopened"
        doc.approved_by = doc.approved_on = doc.closed_by = doc.closed_on = None
        doc.closure_summary = ""
    else:
        frappe.throw(_("That workflow action is not available."), frappe.PermissionError)
    _history(doc, action.replace("_", " ").title(), notes)
    with _mutation("workflow"):
        doc.save()
    return _payload(doc)


def _check_review_people(doc):
    _eligible_user(doc.lead_investigator)
    _eligible_user(doc.reviewer, reviewer=True)
    members = {doc.lead_investigator, doc.reviewer} | {row.user for row in doc.team if row.team_role != "Observer"}
    for row in doc.actions:
        if row.action_status in ("Verified", "Cancelled"):
            continue
        fields = ("verifier",) if row.action_status == "Completed" else ("assigned_to_user", "verifier")
        for field in fields:
            user = row.get(field)
            _eligible_user(user)
            if user and user not in members:
                frappe.throw(_("Add current action owners and verifiers to the team, or reassign the action."))


@frappe.whitelist(methods=["POST"])
def update_action(name, entry_id, action, expected_modified, notes="", file_url=None, verifier=None, assigned_to_user=None):
    doc = _get(name, expected_modified, lock=True)
    if doc.status != "Actions in Progress" and not (doc.status == "Reopened" and action == "reassign"):
        frappe.throw(_("Approve the investigation before progressing corrective actions."))
    row = next((row for row in doc.actions if row.entry_id == entry_id), None)
    if not row:
        frappe.throw(_("Action not found."))
    notes = text(notes)
    user = frappe.session.user
    if not notes:
        frappe.throw(_("Record the action outcome and supporting evidence."))
    if action in ("start", "complete") and row.action_status in ("Open", "In Progress") and user != row.verifier and (row.assigned_to_user == user or is_manager()):
        if action == "complete":
            _check_file(file_url, doc.name)
            row.action_status, row.completion_notes, row.completion_file = "Completed", notes, file_url
            row.completed_by, row.completed_on = user, now_datetime()
        else:
            row.action_status = "In Progress"
    elif action in ("verify", "ineffective") and row.action_status == "Completed" and row.verifier == user and user not in (row.assigned_to_user, row.completed_by):
        row.verification_notes = notes
        if action == "verify":
            row.action_status, row.verified_by, row.verified_on = "Verified", user, now_datetime()
        else:
            row.action_status = "In Progress"
            row.verified_by = row.verified_on = None
    elif action == "cancel" and row.action_status not in ("Verified", "Cancelled") and is_manager():
        row.action_status, row.cancellation_reason = "Cancelled", notes
    elif action == "reassign" and row.action_status not in ("Verified", "Cancelled") and is_manager():
        owner = assigned_to_user or row.assigned_to_user
        verifier = verifier or row.verifier
        if row.action_status == "Completed" and owner != row.assigned_to_user:
            frappe.throw(_("Retain the owner of completed work; reassign its verifier instead."))
        if row.action_status != "Completed":
            _eligible_user(owner)
        _eligible_user(verifier)
        if not owner or not verifier or verifier in (owner, row.completed_by) or (owner, verifier) == (row.assigned_to_user, row.verifier):
            frappe.throw(_("Choose updated action responsibilities and an independent verifier."))
        notes = f"Owner: {row.assigned_to_user} → {owner}. Verifier: {row.verifier} → {verifier}. {notes}"
        row.assigned_to_user, row.verifier = owner, verifier
    else:
        frappe.throw(_("That action update is not available to you."), frappe.PermissionError)
    _history(doc, f"{entry_id}: {action}", notes)
    with _mutation("action"):
        doc.save()
    return _payload(doc)


@frappe.whitelist()
def search_options(kind, query="", source_doctype=None):
    _require_access()
    query = text(query)[:100]
    if kind in ("users", "reviewers"):
        roles = list(MANAGERS) if kind == "reviewers" else [INVESTIGATOR, *MANAGERS]
        names = frappe.get_all("Has Role", filters={"role": ["in", roles], "parenttype": "User"}, pluck="parent")
        names = list(set(names) | {"Administrator"})
        return frappe.get_all("User", filters={"name": ["in", names], "enabled": 1, "user_type": "System User"},
            or_filters={"name": ["like", f"%{query}%"], "full_name": ["like", f"%{query}%"]},
            fields=["name", "full_name as label"], order_by="full_name asc", limit_page_length=30)
    if kind == "projects":
        if not frappe.has_permission("Project", "read"):
            return []
        return frappe.get_list("Project", or_filters={"name": ["like", f"%{query}%"], "project_name": ["like", f"%{query}%"]}, fields=["name", "project_name as label"], limit_page_length=30)
    if kind == "sources" and source_doctype in SOURCES and frappe.has_permission(source_doctype, "read"):
        field = "title" if source_doctype == "EHS Incident" else "description"
        return frappe.get_list(source_doctype, or_filters={"name": ["like", f"%{query}%"], field: ["like", f"%{query}%"]}, fields=["name", f"{field} as label"], limit_page_length=30)
    return []


@frappe.whitelist()
def get_source_details(source_doctype, source_name):
    _require_access()
    if source_doctype not in SOURCES:
        frappe.throw(_("Unsupported incident source."))
    doc = frappe.get_doc(source_doctype, source_name)
    doc.check_permission("read")
    if source_doctype == "EHS Incident":
        return {"title": doc.title, "incident_datetime": doc.incident_datetime, "description": doc.description,
            "project": doc.project, "site_location": doc.location, "classification": doc.classification}
    return {"title": str(doc.description or doc.name)[:140], "description": doc.description,
        "incident_datetime": f"{doc.date_occured} 00:00:00" if doc.date_occured else None, "incident_time_precision": "Date only",
        "project": doc.link_project, "site_location": doc.work_area, "classification": doc.classification,
        "actual_severity": doc.consequence if doc.consequence != "PENDING" else "",
        "external_reference": doc.client_reference}
