"""Persisted shift checks: PERI records the discussion; a human confirms it."""
from __future__ import annotations

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import cint, date_diff, getdate, now_datetime, today

from verto.api.mobile import voice_jha_review as review
from verto.api.mobile.voice_jha_fieldwork import locked_jha, control_state

DOCTYPE = "JHA Shift Revalidation"
CATEGORIES = {
    "crew": "Have the people, roles or crew understanding changed since this JHA was signed?",
    "equipment": "Has any plant, equipment, tooling or isolation arrangement changed?",
    "environment": "Have the work area, access, weather or nearby activities changed?",
    "method": "Has the job scope, work sequence or method changed?",
    "controls": "Are any hazards, controls or hold points different, missing or ineffective?",
}
OPEN_STATUSES = {"In Progress", "Awaiting Confirmation"}
TOOLS = {"get_current_jha_state", "record_jha_shift_check"}


def _checks(doc):
    return json.loads(doc.get("checks") or "{}")


def serialize_review(doc):
    checks = _checks(doc)
    category = next((key for key in CATEGORIES if key not in checks), None) if doc.status == "In Progress" else None
    return {"name": doc.name, "jha": doc.jha, "revision": doc.revision, "shift_date": str(doc.shift_date),
        "shift": doc.shift, "status": doc.status, "checks": checks, "next_category": category,
        "next_question": CATEGORIES.get(category, ""), "started_by": doc.started_by,
        "started_at": str(doc.started_at), "confirmed_by": doc.get("confirmed_by"),
        "confirmed_at": str(doc.confirmed_at) if doc.get("confirmed_at") else None,
        "replacement_jha": doc.get("replacement_jha"), "change_summary": change_summary(doc)}


def shift_reviews(jha):
    names = frappe.get_all(DOCTYPE, filters={"jha": jha.name}, pluck="name", order_by="creation desc", limit_page_length=10)
    return [serialize_review(frappe.get_doc(DOCTYPE, name)) for name in names]


def get_review(jha, name):
    doc = frappe.get_doc(DOCTYPE, name)
    if doc.jha != jha.name or cint(doc.revision) != cint(jha.revision):
        frappe.throw(_("This shift review belongs to a different JHA revision."), frappe.PermissionError)
    return doc


def _save(doc):
    doc.flags.allow_jha_field_mutation = True
    return doc.save(ignore_permissions=True)


def change_summary(doc):
    return "; ".join(f"{category}: {value['notes']}" for category, value in _checks(doc).items() if value.get("changed"))


@frappe.whitelist(methods=["POST"])
def begin_jha_shift_review(jha_name: str, shift_date: str, shift: str, confirmation=0):
    jha = locked_jha(jha_name)
    if jha.jha_status != "Signed" or not cint(confirmation):
        frappe.throw(_("Start a shift review from a signed JHA and confirm the crew will review current conditions."), frappe.ValidationError)
    try:
        date = getdate(shift_date)
    except (ValueError, TypeError):
        frappe.throw(_("Choose a valid shift date."), frappe.ValidationError)
    if shift not in {"Day", "Night"} or date_diff(today(), date) not in (0, 1):
        frappe.throw(_("Choose a Day or Night shift starting today or yesterday."), frappe.ValidationError)
    key = hashlib.sha256(f"{jha.name}|{date}|{shift}".encode()).hexdigest()
    existing = frappe.db.get_value(DOCTYPE, {"review_key": key}, "name")
    if existing:
        return serialize_review(get_review(jha, existing))
    doc = frappe.get_doc({"doctype": DOCTYPE, "jha": jha.name, "revision": jha.revision,
        "work_summary": jha.work_summary, "project": jha.project, "shift_date": date, "shift": shift,
        "status": "In Progress", "checks": "{}", "tool_audit": "[]", "review_key": key,
        "started_by": frappe.session.user, "started_at": now_datetime()})
    doc.flags.allow_jha_field_mutation = True
    doc.insert(ignore_permissions=True)
    return serialize_review(doc)


@frappe.whitelist(methods=["POST"])
def confirm_jha_shift_review(jha_name: str, shift_review: str, confirmation=0):
    jha = locked_jha(jha_name)
    doc = get_review(jha, shift_review)
    if jha.jha_status != "Signed" or not cint(confirmation):
        frappe.throw(_("Confirm the shift review against the current signed revision."), frappe.ValidationError)
    if doc.status == "No Change":
        return serialize_review(doc)
    checks = _checks(doc)
    if (doc.status != "Awaiting Confirmation" or set(checks) != set(CATEGORIES)
        or any(value.get("changed") for value in checks.values())):
        frappe.throw(_("Complete every shift check without changes before confirming. Identified changes need a new JHA revision."), frappe.ValidationError)
    if any(control["status"] in {"Failed", "Recheck Required"} for control in control_state(jha)):
        frappe.throw(_("Resolve failed or stale critical-control checks before confirming unchanged conditions."), frappe.ValidationError)
    from verto.api.mobile.voice_jha_workpack import outstanding_references
    if outstanding_references(jha):
        frappe.throw(_("Check outstanding, expired or changed permit/isolation references before confirming unchanged conditions."), frappe.ValidationError)
    doc.status = "No Change"
    doc.confirmed_by = frappe.session.user
    doc.confirmed_at = now_datetime()
    _save(doc)
    return serialize_review(doc)


@frappe.whitelist(methods=["POST"])
def begin_shift_change(jha_name: str, shift_review: str, confirmation=0):
    from verto.api.mobile.voice_jha_changes import begin_jha_change
    review._require_login()
    jha = review._get_jha(jha_name, require_write=True)
    doc = get_review(jha, shift_review)
    if doc.status != "Change Required" or not cint(confirmation):
        frappe.throw(_("Confirm the identified shift changes before starting their change review."), frappe.ValidationError)
    snapshot = begin_jha_change(jha_name, confirmation=1)
    doc.reload()
    if doc.get("replacement_jha") == snapshot["name"]:
        return snapshot
    # Carry the crew's description into the new interview; placement and scope
    # still require explicit crew confirmation through normal change management.
    replacement = frappe.get_doc(review.JHA_DOCTYPE, snapshot["name"])
    if replacement.change_management_stage == "Describe Change" and not replacement.change_summary:
        replacement.change_summary = change_summary(doc)
        replacement.flags.allow_jha_change_mutation = True
        replacement.save()
        from verto.api.mobile.voice_jha_progress import serialize_jha
        snapshot = serialize_jha(replacement)
    doc.replacement_jha = snapshot["name"]
    _save(doc)
    return snapshot


def shift_review_tools():
    return [
        {"type": "function", "name": "get_current_jha_state", "description": "Read the signed JHA and this human-started shift review, including the next missing check.",
         "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
        {"type": "function", "name": "record_jha_shift_check",
         "description": "Record one explicit crew answer to a shift check. changed=true requires the crew's description. This never changes, signs or authorises the JHA and cannot confirm the final review for a human.",
         "parameters": {"type": "object", "properties": {"category": {"type": "string", "enum": list(CATEGORIES)},
              "changed": {"type": "boolean"}, "notes": {"type": "string"}},
              "required": ["category", "changed", "notes"], "additionalProperties": False}},
    ]


def shift_instructions(jha, config):
    from verto.api.mobile.voice_jha import _build_conversation_style_instructions
    state = jha.flags.shift_review
    return f"""You are PERI running a short START-OF-SHIFT REVALIDATION, not developing the job again.
JHA: {jha.name}, signed revision {jha.revision}; Work Summary: {jha.work_summary_title or jha.work_summary}.
Shift review persisted state: {json.dumps(state, default=str)}
Ask the persisted next_question. After each explicit answer, call record_jha_shift_check and immediately
ask the next_question returned by the server. Do not ask whether the crew is ready to proceed.
Work through crew, equipment, environment, method and controls, one question at a time.
Ask whether conditions differ from the signed JHA. A 'no' to a change question means changed=false.
If a change is identified, briefly clarify it and record changed=true with the crew's description.
When status becomes Change Required, ask the user to select Review Changes with PERI on screen;
this opens a separate revision. Do not continue the unchanged checklist or edit the signed JHA.
When status becomes Awaiting Confirmation, briefly read back that no changes were identified,
then ask the human to review the recorded checks and select Confirm No Changes on screen.
Never claim to have signed, approved, verified a critical control, cleared a hold point or authorised work.
No Change records this shift discussion only. Existing site permits, isolations and authorisations still apply.
The signed JHA and prior signatures remain intact. Never invent crew answers or site conditions.
Use get_current_jha_state to resume without repeating completed checks. Once complete, remain available
for questions until Disconnect Voice. There is no voice tool to confirm the final human review.
{_build_conversation_style_instructions(config)}"""


def execute_shift_tool(jha_name, shift_review, tool_name, arguments, call_id):
    from verto.api.mobile.voice_jha_progress import serialize_jha
    review._require_login()
    if tool_name not in TOOLS:
        frappe.throw(_("Only shift-review tools are available in this conversation."), frappe.PermissionError)
    jha = review._get_jha(jha_name, require_write=tool_name != "get_current_jha_state")
    if tool_name == "record_jha_shift_check":
        jha = locked_jha(jha_name, allow_closed=True)
    doc = get_review(jha, shift_review)
    replayed = False
    if tool_name == "record_jha_shift_check":
        if not call_id or len(call_id) > 200:
            frappe.throw(_("A valid tool call ID is required."), frappe.ValidationError)
        audit = json.loads(doc.get("tool_audit") or "[]")
        replayed = any(item["call_id"] == call_id for item in audit)
        if not replayed:
            if jha.jha_status != "Signed" or jha.get("replacement_jha") or doc.status != "In Progress":
                frappe.throw(_("This shift discussion is complete or requires human action."), frappe.PermissionError)
            try:
                args = json.loads(arguments) if isinstance(arguments, str) else arguments
            except (ValueError, TypeError):
                frappe.throw(_("Supply a valid shift-check answer."), frappe.ValidationError)
            if not isinstance(args, dict):
                frappe.throw(_("Supply a valid shift-check answer."), frappe.ValidationError)
            category, changed, notes = args.get("category"), args.get("changed"), str(args.get("notes") or "").strip()
            checks = _checks(doc)
            expected = next((key for key in CATEGORIES if key not in checks), None)
            if category != expected or not isinstance(changed, bool) or len(notes) > 2000 or (changed and not notes):
                frappe.throw(_("Answer the current shift question and describe any identified change."), frappe.ValidationError)
            checks[category] = {"changed": changed, "notes": notes, "recorded_at": str(now_datetime()), "recorded_by": frappe.session.user}
            doc.checks = json.dumps(checks)
            doc.status = "Change Required" if changed else "Awaiting Confirmation" if set(checks) == set(CATEGORIES) else "In Progress"
            if changed:
                jha.jha_status = "Review Required - Work Changed"
                jha.flags.allow_jha_review_mutation = True
                review._append_review_audit(jha, "shift_change_identified", {
                    "shift_review": doc.name, "category": category, "description": notes,
                })
                jha.save()
            audit.append({"call_id": call_id, "category": category, "at": str(now_datetime()), "user": frappe.session.user})
            doc.tool_audit = json.dumps(audit)
            _save(doc)
    state = serialize_review(doc)
    message = state["next_question"] or (
        "Review the recorded checks and select Confirm No Changes on screen. Human confirmation is required."
        if doc.status == "Awaiting Confirmation" else
        "Select Review Changes with PERI on screen to reassess the identified change in a new revision."
        if doc.status == "Change Required" else "Shift review recorded. Remain available until Disconnect Voice.")
    snapshot = serialize_jha(jha)
    snapshot["shift_review"] = state
    return {"ok": True, "replayed": replayed, "tool_name": tool_name,
            "result": {"shift_review": state, "message": message}, "jha": snapshot}
