"""Prepare a checked paper JHA for human review without a voice interview."""
from __future__ import annotations

import hashlib
import json
from functools import partial
from email.utils import parseaddr
from html import escape
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, get_url, now_datetime, validate_email_address

from verto.api.mobile import voice_jha_review as review
from verto.api.mobile.jha_photo_content import normalise_participants
from verto.api.mobile.voice_jha_fieldwork import locked_jha
from verto.api.mobile.voice_jha_permissions import get_assigned_users, _is_privileged_user, user_can_access_work_summary

FIELDS = ("paper_review_mode", "paper_review_team_leader", "paper_review_recipient", "paper_review_requested_by",
          "paper_review_requested_at", "paper_review_fingerprint", "paper_review_snapshot", "paper_review_notes",
          "paper_review_status", "paper_review_email_queue", "paper_review_error", "paper_review_sent_at")
EDITABLE = {"Draft", "Voice Discussion in Progress", "Incomplete - Actions Required"}


def validate_mutations(doc):
    if doc.flags.get("allow_jha_paper_review_mutation"):
        return
    before = doc.get_doc_before_save() if not doc.is_new() else None
    for field in FIELDS:
        current, previous = doc.get(field), before.get(field) if before else None
        if field == "paper_review_mode":
            current, previous = current or "Guided", previous or "Guided"
        elif field.endswith(("_at",)):
            current = str(get_datetime(current)) if current else ""
            previous = str(get_datetime(previous)) if previous else ""
        if str(current or "") != str(previous or ""):
            frappe.throw(_("Use the paper JHA review workflow to change its preparation or delivery details."), frappe.PermissionError)


def can_prepare(jha):
    return bool(jha.get("photo_import") and not jha.get("previous_jha") and not jha.get("replacement_jha")
                and jha.jha_status in EDITABLE and not cint(jha.get("review_completed"))
                and jha.get("paper_review_mode") != "Automatic")


def reviewer_options(jha):
    names = get_assigned_users(jha.work_summary)
    if _is_privileged_user(frappe.session.user):
        names.add(frappe.session.user)
    if not names:
        return []
    users = frappe.get_all("User", filters={"name": ["in", sorted(names)], "enabled": 1},
                           fields=["name", "full_name", "email"], order_by="full_name asc")
    return [{"value": row.name, "label": f"{row.full_name or row.name} · {row.name}"} for row in users
            if row.name != "Guest" and row.email]


def _reviewer(jha, user):
    if not user or user == "Guest" or not frappe.db.exists("User", user) or not user_can_access_work_summary(jha.work_summary, user):
        frappe.throw(_("Select a team leader assigned to this Work Summary, or a System Manager."), frappe.PermissionError)
    person = frappe.get_doc("User", user)
    if not cint(person.enabled) or not all(frappe.has_permission(jha.doctype, ptype, doc=jha, user=user) for ptype in ("read", "write")):
        frappe.throw(_("The selected team leader must have access to review this JHA."), frappe.PermissionError)
    value = str(person.email or "").strip()
    display, address = parseaddr(value)
    if not value or display or address != value or any(character in value for character in "\r\n,;"):
        frappe.throw(_("The selected team leader needs one valid email address on their User account."), frappe.ValidationError)
    return validate_email_address(value, throw=True)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _content_hash(jha):
    def rows(field, columns):
        return [[str(row.get(key) or "") for key in columns] for row in jha.get(field) or []]
    return _hash([jha.revision, jha.photo_import, jha.source_revision,
        rows("work_steps", ("sequence", "activity", "paper_hold_point", "hold_or_pause_point")),
        rows("hazards_and_controls", ("work_step_sequence", "hazard_or_energy_source", "existing_controls",
            "additional_controls", "critical_control", "control_owner", "critical_risk_categories", "exposure_mechanisms")),
        rows("participants", ("participant_name", "role", "present_for_discussion"))])


def _notes(jha, source):
    notes = [f"Original reading: {value}" for value in source.get("uncertainties") or []]
    for step in jha.work_steps or []:
        hazards = [row for row in jha.hazards_and_controls or [] if cint(row.work_step_sequence) == cint(step.sequence)]
        if not hazards:
            notes.append(f"Step {step.sequence}: no hazard was recorded on the checked paper JHA.")
        for hazard in hazards:
            if not (hazard.existing_controls or hazard.additional_controls):
                notes.append(f"Step {step.sequence}: confirm controls for {hazard.hazard_or_energy_source}.")
            if hazard.critical_control and not hazard.control_owner:
                notes.append(f"Step {step.sequence}: confirm the owner of critical control {hazard.critical_control}.")
        if not step.get("paper_hold_point") and not cint(step.get("hold_point_confirmed")):
            notes.append(f"Step {step.sequence}: no hold-point decision was recorded on the paper JHA.")
    return notes


def prepare_draft(jha, team_leader, participants):
    try:
        people = normalise_participants(participants)
    except (TypeError, ValueError) as exc:
        frappe.throw(_(str(exc)), frappe.ValidationError)
    fingerprint = _hash([jha.photo_import, team_leader, people])
    if jha.get("paper_review_mode") == "Automatic":
        if fingerprint != jha.get("paper_review_fingerprint"):
            frappe.throw(_("This paper JHA has already been sent for review with different details."), frappe.ValidationError)
        return
    if not can_prepare(jha):
        frappe.throw(_("Automatic preparation is available only for an editable, imported paper JHA."), frappe.ValidationError)
    if jha.source_has_changed():
        frappe.throw(_("The planned work changed after the paper import. Reassess that change before sending for review."), frappe.ValidationError)
    from verto.api.mobile.voice_jha_photos import _record
    source = _record(jha, jha.photo_import)
    if source.status != "Imported" or not jha.work_steps:
        frappe.throw(_("Check and import the paper JHA before sending it for review."), frappe.ValidationError)
    recipient = _reviewer(jha, team_leader)
    previous_people = {str(row.participant_name).casefold(): row for row in jha.participants or []}
    jha.set("participants", [])
    for index, person in enumerate(people, 1):
        previous = previous_people.get(person["participant_name"].casefold())
        jha.append("participants", {**person, "source_participant_identifier": previous.get("source_participant_identifier") if previous else f"paper-person-{index}",
            "employee": previous.get("employee") if previous else None,
            "present_for_discussion": 1, "transcription_consent": cint(previous.get("transcription_consent")) if previous else 0, "acknowledged": 0})
    source_content = json.loads(source.reviewed_content)
    # Earlier imports predate the dedicated written hold-point field.
    for index, step in enumerate(jha.work_steps):
        original = (source_content.get("steps") or [])
        if not step.get("paper_hold_point") and not cint(step.get("hold_point_confirmed")) and index < len(original) and step.activity == original[index]["activity"]:
            step.paper_hold_point = original[index].get("hold_point") or ""
    jha.paper_review_mode = "Automatic"
    jha.paper_review_team_leader = team_leader
    jha.paper_review_recipient = recipient
    jha.paper_review_requested_by = frappe.session.user
    jha.paper_review_requested_at = now_datetime()
    jha.paper_review_fingerprint = fingerprint
    jha.paper_review_notes = json.dumps(_notes(jha, source_content))
    jha.paper_review_snapshot = _content_hash(jha)
    jha.paper_review_status = "Pending"
    jha.jha_status = "Ready for Team Review"
    jha.flags.allow_jha_paper_review_mutation = True
    jha.flags.allow_jha_review_mutation = True
    review._append_review_audit(jha, "paper_prepared_for_review", {"source": source.name, "team_leader": team_leader,
        "basis": "Checked paper JHA; guided voice discussion skipped", "participant_count": len(people)})
    # Do not fabricate voice completion, consent, verification, signatures or approval.
    from verto.api.mobile.voice_jha_progress import sync_facilitation_fields
    sync_facilitation_fields(jha)
    jha.save(ignore_permissions=True)
    _schedule(jha.name)


@frappe.whitelist(methods=["POST"])
def prepare_paper_jha_for_review(jha_name: str, team_leader: str, participants, confirmation=0):
    jha = locked_jha(jha_name, allow_closed=True)
    if not cint(confirmation):
        frappe.throw(_("Confirm the checked paper JHA and the people who participated before sending for review."), frappe.ValidationError)
    prepare_draft(jha, team_leader, participants)
    from verto.api.mobile.voice_jha_progress import serialize_jha
    return {"jha": serialize_jha(jha), "paper_review": review_state(jha)}


def _queue(jha):
    return frappe.db.get_value("Email Queue", jha.paper_review_email_queue, ["name", "status", "modified", "error"], as_dict=True) if jha.get("paper_review_email_queue") else None


def review_state(jha):
    if jha.get("paper_review_mode") != "Automatic":
        return None
    return {"team_leader": jha.paper_review_team_leader, "recipient": jha.paper_review_recipient,
        "review_completed": bool(cint(jha.get("review_completed"))),
        "status": jha.paper_review_status, "requested_at": str(jha.paper_review_requested_at or ""),
        "sent_at": str(jha.paper_review_sent_at or ""), "notes": json.loads(jha.paper_review_notes or "[]"),
        "error": jha.paper_review_error or "", "can_retry": jha.paper_review_status == "Failed" and jha.has_permission("write")}


def _set_delivery(jha, **values):
    updates = {f"paper_review_{key}": value for key, value in values.items()}
    frappe.db.set_value(jha.doctype, jha.name, updates, update_modified=False)
    jha.update(updates)


def _current(jha):
    return bool(jha.get("paper_review_mode") == "Automatic" and jha.jha_status == "Ready for Team Review"
                and not jha.get("replacement_jha") and not cint(jha.get("review_completed"))
                and jha.paper_review_snapshot == _content_hash(jha) and not jha.source_has_changed())


def _cancel(jha, reason):
    queue = _queue(jha)
    if queue and queue.status in {"Sent", "Sending"}:
        _set_delivery(jha, status=queue.status, sent_at=queue.modified if queue.status == "Sent" else None)
        return
    if queue:
        frappe.db.set_value("Email Queue", queue.name, {"status": "Error", "error": reason})
    _set_delivery(jha, status="Cancelled", error=reason)


def _enqueue(name):
    try:
        frappe.enqueue("verto.api.mobile.voice_jha_paper_review.prepare_review_email", queue="short", timeout=300,
                       job_id=f"jha-paper-review-{name}", deduplicate=True, jha_name=name)
    except Exception:
        frappe.log_error(title="Paper JHA review could not be scheduled", message=frappe.get_traceback())


def _schedule(name):
    frappe.db.after_commit.add(partial(_enqueue, name))


def _lock(name):
    frappe.db.sql("select name from `tabDigital Job Hazard Analysis` where name=%s for update", name)
    return frappe.get_doc(review.JHA_DOCTYPE, name)


def _message(jha, searches):
    def excerpt(value, limit=700):
        value = str(value or "Not recorded.")
        return escape(value if len(value) <= limit else value[:limit] + "…")

    def reference(item):
        return f"{item.get('source_system') or ''} {item.get('source_reference') or item['name']} · {item.get('incident_date') or 'Date not recorded'}"

    url = get_url(f"/verto-mobile/voice-jha/{quote(jha.work_summary, safe='')}?jha={quote(jha.name, safe='')}")
    paragraphs = [f"<p>PERI has prepared the checked paper JHA for <strong>{escape(jha.work_summary_title or jha.work_summary)}</strong>.</p>",
        "<p>The guided voice interview was skipped. Team leader review (Supervisor or above) and personal crew sign-on are still required.</p>",
        f'<p><a href="{escape(url, quote=True)}">Review JHA {escape(jha.name)} · Revision {cint(jha.revision)}</a></p>']
    notes = json.loads(jha.paper_review_notes or "[]")
    if notes:
        paragraphs.append("<h3>Items to check during review</h3><ul>" + "".join(f"<li>{excerpt(note, 400)}</li>" for note in notes[:40]) + "</ul>")
        if len(notes) > 40:
            paragraphs.append(f"<p>{len(notes) - 40} further items are listed in the JHA review screen.</p>")
    unique = {}
    for search in searches:
        paragraphs.append(f"<h3>Step {cint(search['step'])}: {excerpt(search['activity'], 200)}</h3>")
        incidents = search["incidents"]
        if not incidents:
            paragraphs.append("<p>Incident lookup unavailable.</p>" if search["unavailable"] else "<p>No matching incident was found in the accessible dataset. This does not establish absence of risk.</p>")
        for item in incidents:
            link = get_url(item["record_url"])
            paragraphs.append(f'<p><a href="{escape(link, quote=True)}">{escape(reference(item))}</a></p>')
            matched = ', '.join(str(value) for values in (item.get('matched_on') or {}).values() for value in values)
            paragraphs.append(f"<p>Why relevant: {excerpt(', '.join(search['hazards']), 300)}. Matched evidence: {excerpt(matched, 300)}.</p>")
            unique.setdefault(item["name"], {"incident": item, "steps": []})["steps"].append(cint(search["step"]))
        if search["limited"]:
            paragraphs.append("<p>The search covered a bounded set of records; further incidents may exist.</p>")
    if unique:
        paragraphs.append("<h3>Incident excerpts</h3><p>Open the source links for complete findings and action lists. Up to 12 incident excerpts are included below; all matched sources are linked against their steps above.</p>")
    for matched in list(unique.values())[:12]:
        item = matched["incident"]
        paragraphs.extend([f"<p><strong>{escape(reference(item))} · {excerpt(item.get('title'), 200)}</strong> · Related steps: {', '.join(map(str, matched['steps']))}</p>",
            f"<p>{excerpt(item.get('incident_summary'))}</p>",
            f"<p>Recorded findings: {excerpt(item.get('investigation_findings'))}</p>",
            f"<p>Recorded investigation actions: {excerpt(item.get('investigation_actions'))}</p>"])
        for action in (item.get("actions") or [])[:3]:
            paragraphs.append(f"<p>{excerpt(action.get('source_action_reference'), 140)}: {excerpt(action.get('action_description'), 500)} · Status: {excerpt(action.get('action_status'), 140)} · Effectiveness: {excerpt(action.get('effectiveness_notes'), 300)}</p>")
        if item.get("recommended_controls"):
            paragraphs.append(f"<p>Historical recommendations: {excerpt(item['recommended_controls'])}</p>")
    paragraphs.append("<p>Historical incident actions and their status do not verify today's controls or authorise this work.</p>")
    return "".join(paragraphs)


def _find_incidents(jha):
    from verto.api.mobile.voice_jha_incidents import find_incident_learning
    from verto.api.mobile import jha_risk_signals as risk
    summaries = []
    # Search once per job step using all its hazards and controls, rather than
    # repeating the same incident lookup for every row.
    for step in jha.work_steps or []:
        hazards = [h for h in jha.hazards_and_controls or [] if cint(h.work_step_sequence) == cint(step.sequence)]
        context = "\n".join([step.activity] + ["\n".join(str(h.get(key) or "") for key in
            ("hazard_or_energy_source", "existing_controls", "additional_controls", "critical_control")) for h in hazards])
        try:
            signals = [risk.signals(step.activity)] + [risk.signals("\n".join(str(h.get(key) or "") for key in
                ("hazard_or_energy_source", "existing_controls", "additional_controls", "critical_control")),
                h.get("critical_risk_categories") or (), h.get("exposure_mechanisms") or ()) for h in hazards]
            found = find_incident_learning(context,
                critical_risks=sorted({label for item in signals for label in item["critical_risks"]}),
                mechanisms=sorted({label for item in signals for label in item["mechanisms"]}))
            found["search_limited"] = bool(found.get("search_limited") or len(context) > 10000)
        except Exception:
            frappe.log_error(title="Paper JHA incident lookup failed", message=frappe.get_traceback())
            found = {"status": "unavailable", "incidents": [], "signals": {}, "search_limited": False}
        summaries.append({"step": step.sequence, "activity": step.activity, "hazards": [h.hazard_or_energy_source for h in hazards],
            "incidents": found["incidents"], "unavailable": found["status"] == "unavailable", "limited": found.get("search_limited", False)})
        for hazard in hazards:
            identifier = hazard.get("source_hazard_identifier") or hazard.name
            jha.set("incident_references", [row for row in jha.get("incident_references") or [] if row.hazard_identifier != identifier])
            jha.append("incident_references", {"hazard_identifier": identifier, "work_step_sequence": step.sequence,
                "jha_revision": jha.revision, "hazard_fingerprint": risk.fingerprint(step, hazard), "search_status": found["status"],
                "search_limited": cint(found.get("search_limited")), "detected_signals": json.dumps(found["signals"]),
                "incident_matches": json.dumps([{"name": item["name"], "modified": item["modified"], "matched_on": item["matched_on"]} for item in found["incidents"]]),
                "searched_at": now_datetime()})
    jha.flags.allow_jha_incident_mutation = True
    jha.save(ignore_permissions=True)
    return summaries


def prepare_review_email(jha_name):
    from verto.api.mobile.voice_jha_email import _system_user
    with _system_user():
        jha = _lock(jha_name)
        if not _current(jha):
            _cancel(jha, "This JHA no longer needs the requested team leader review.")
            return
        if jha.get("paper_review_email_queue"):
            if jha.paper_review_status in {"Queued", "Sending"}:
                frappe.db.after_commit.add(partial(send_review_email, jha.name))
            return
        frappe.db.savepoint("paper_jha_review_email")
        try:
            recipient = _reviewer(jha, jha.paper_review_team_leader)
            if recipient != jha.paper_review_recipient:
                raise ValueError("The team leader's email address changed. Check the review destination.")
            frappe.set_user(jha.paper_review_team_leader)
            try:
                searches = _find_incidents(jha)
            finally:
                frappe.set_user("Administrator")
            if not _current(jha):
                _cancel(jha, "The planned work changed while its incident briefing was prepared.")
                return
            title = " ".join(str(jha.work_summary_title or jha.work_summary).split())
            queue = frappe.sendmail(recipients=[recipient], subject=f"Paper JHA ready for review: {title} | {jha.name} | Rev {cint(jha.revision)}",
                message=_message(jha, searches), delayed=True, add_unsubscribe_link=0,
                reference_doctype=jha.doctype, reference_name=jha.name)
            if not queue or not queue.name:
                raise ValueError("The review email could not be added to Email Queue.")
            _set_delivery(jha, email_queue=queue.name, status="Queued", error="")
            frappe.db.after_commit.add(partial(send_review_email, jha.name))
        except Exception:
            frappe.db.rollback(save_point="paper_jha_review_email")
            jha.reload()
            _set_delivery(jha, status="Failed", error="Review preparation failed. Check the Error Log and retry.")
            frappe.log_error(title="Paper JHA review email preparation failed", message=frappe.get_traceback())


def send_review_email(jha_name):
    from verto.api.mobile.voice_jha_email import _system_user
    with _system_user():
        jha = _lock(jha_name)
        try:
            recipient = _reviewer(jha, jha.paper_review_team_leader)
        except (frappe.PermissionError, frappe.ValidationError):
            _cancel(jha, "The team leader no longer has access or a valid review email address.")
            frappe.db.commit()
            return
        try:
            if not _current(jha) or recipient != jha.paper_review_recipient:
                _cancel(jha, "The JHA or its review destination has changed.")
                frappe.db.commit()
                return
            info = _queue(jha)
            if not info:
                raise ValueError("The review email is unavailable.")
            if info.status in {"Sent", "Sending"}:
                _set_delivery(jha, status=info.status, sent_at=info.modified if info.status == "Sent" else None)
            else:
                queue = frappe.get_doc("Email Queue", info.name)
                if not queue.can_send_now():
                    raise ValueError("Email delivery is suspended, muted or unavailable.")
                _set_delivery(jha, status="Sending")
                queue.send()
                info = _queue(jha)
                _set_delivery(jha, status="Sent" if info and info.status == "Sent" else "Failed",
                    sent_at=info.modified if info and info.status == "Sent" else None,
                    error="" if info and info.status == "Sent" else "Email delivery failed. Check Email Queue and retry.")
        except Exception:
            info = _queue(jha)
            if info and info.status in {"Sent", "Sending"}:
                _set_delivery(jha, status=info.status, sent_at=info.modified if info.status == "Sent" else None)
            else:
                _set_delivery(jha, status="Failed", error="Email delivery failed. Check Email Queue and the team leader's access before retrying.")
            frappe.log_error(title="Paper JHA review immediate email failed", message=frappe.get_traceback())
        frappe.db.commit()


@frappe.whitelist(methods=["POST"])
def retry_paper_review_email(jha_name: str, confirmation=0):
    jha = locked_jha(jha_name, allow_closed=True)
    if not cint(confirmation) or not _current(jha):
        frappe.throw(_("Confirm a retry against the current paper JHA awaiting team leader review."), frappe.ValidationError)
    if _reviewer(jha, jha.paper_review_team_leader) != jha.paper_review_recipient:
        frappe.throw(_("The review destination changed. Check the team leader's user account."), frappe.ValidationError)
    info = _queue(jha)
    if info and info.status in {"Sent", "Sending"}:
        return review_state(jha)
    if info and info.status == "Error":
        frappe.db.set_value("Email Queue", info.name, {"status": "Not Sent", "error": "", "retry": 0})
    _set_delivery(jha, status="Queued" if info else "Pending", error="")
    _schedule(jha.name)
    return review_state(jha)


def jha_updated(doc, method=None):
    if doc.get("paper_review_mode") == "Automatic" and doc.get("paper_review_status") in {"Pending", "Queued", "Sending", "Failed"} and not _current(doc):
        _cancel(doc, "The JHA was reviewed, replaced or changed before this review request was sent.")


def reconcile_review_emails():
    from verto.api.mobile.voice_jha_email import _system_user
    with _system_user():
        names = frappe.get_all(review.JHA_DOCTYPE, filters={"paper_review_status": ["in", ["Pending", "Queued", "Sending", "Failed"]]}, pluck="name", limit_page_length=100)
        for name in names:
            jha = _lock(name)
            if not _current(jha):
                _cancel(jha, "This JHA no longer needs the requested review.")
            elif jha.paper_review_status == "Pending":
                _schedule(name)
            elif jha.paper_review_status in {"Queued", "Sending"}:
                frappe.db.after_commit.add(partial(send_review_email, name))
