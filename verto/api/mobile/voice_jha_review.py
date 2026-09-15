from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from verto.api.mobile.voice_jha_permissions import user_can_access_work_summary


JHA_DOCTYPE = "Digital Job Hazard Analysis"
MAX_SIGNATURE_LENGTH = 1_500_000
MAX_REVIEW_NOTES_LENGTH = 10_000
MAX_AUDIT_ENTRIES = 300


def _require_login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _get_jha(jha_name: str, *, require_write: bool = False):
    if not jha_name or not frappe.db.exists(JHA_DOCTYPE, jha_name):
        frappe.throw(_("Digital JHA was not found."), frappe.DoesNotExistError)

    doc = frappe.get_doc(JHA_DOCTYPE, jha_name)
    permission = "write" if require_write else "read"
    if not doc.has_permission(permission):
        frappe.throw(_("You cannot access this Digital JHA."), frappe.PermissionError)
    if not user_can_access_work_summary(doc.work_summary):
        frappe.throw(_("This Digital JHA is not linked to work assigned to you."), frappe.PermissionError)

    if hasattr(doc, "mark_review_required_if_source_changed"):
        changed = doc.mark_review_required_if_source_changed()
        if changed:
            doc.flags.allow_jha_review_mutation = True
            doc.save(ignore_permissions=True)

    return doc


def _signature(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        frappe.throw(_("A signature is required."), frappe.ValidationError)
    if len(value) > MAX_SIGNATURE_LENGTH:
        frappe.throw(_("The signature image is unexpectedly large."), frappe.ValidationError)
    if not value.startswith(("data:image/png;base64,", "data:image/jpeg;base64,")):
        frappe.throw(_("The signature must be a captured PNG or JPEG image."), frappe.ValidationError)
    return value


def _reviewer_name(user: str) -> str:
    return (
        frappe.db.get_value("User", user, "full_name")
        or frappe.db.get_value("User", user, "first_name")
        or user
    )


def _append_review_audit(doc, event: str, details: dict | None = None):
    entries = []
    raw = str(doc.get("review_audit_log") or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                entries = parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            entries = []

    entries.append(
        {
            "at": str(now_datetime()),
            "user": frappe.session.user,
            "event": event,
            "details": details or {},
        }
    )
    doc.review_audit_log = json.dumps(entries[-MAX_AUDIT_ENTRIES:], default=str)


def _serialize_review(doc) -> dict:
    participants = []
    for row in doc.participants or []:
        participants.append(
            {
                "name": row.name,
                "participant_name": row.participant_name,
                "employee": row.employee,
                "role": row.role,
                "present_for_discussion": cint(row.present_for_discussion),
                "transcription_consent": cint(row.transcription_consent),
                "acknowledged": cint(row.acknowledged),
                "acknowledged_at": row.acknowledged_at,
                "acknowledged_by_user": row.get("acknowledged_by_user"),
                "acknowledgement_signature": row.get("acknowledgement_signature"),
            }
        )

    return {
        "name": doc.name,
        "status": doc.jha_status,
        "revision": doc.revision,
        "review_completed": cint(doc.get("review_completed")),
        "reviewed_by": doc.get("reviewed_by"),
        "reviewer_name": doc.get("reviewer_name"),
        "reviewed_at": doc.get("reviewed_at"),
        "review_signature": doc.get("review_signature"),
        "review_notes": doc.get("review_notes") or "",
        "signed_at": doc.get("signed_at"),
        "signed_by_user": doc.get("signed_by_user"),
        "participants": participants,
    }


def _present_participants(doc):
    return [row for row in (doc.participants or []) if cint(row.present_for_discussion)]


def _all_required_participants_acknowledged(doc) -> bool:
    participants = _present_participants(doc)
    return bool(participants) and all(cint(row.acknowledged) for row in participants)


@frappe.whitelist(methods=["GET"])
def get_jha_review_state(jha_name: str):
    _require_login()
    return _serialize_review(_get_jha(jha_name))


@frappe.whitelist(methods=["POST"])
def complete_human_review(
    jha_name: str,
    signature: str,
    confirmation=0,
    review_notes: str = "",
):
    _require_login()
    if not cint(confirmation):
        frappe.throw(
            _("Confirm that you have reviewed the JHA before signing the review."),
            frappe.ValidationError,
        )

    doc = _get_jha(jha_name, require_write=True)
    if doc.jha_status != "Ready for Team Review":
        frappe.throw(
            _("Human review can only be completed when the JHA is Ready for Team Review."),
            frappe.ValidationError,
        )
    if cint(doc.get("review_completed")):
        return _serialize_review(doc)

    present = _present_participants(doc)
    if not present:
        frappe.throw(_("At least one present participant is required before review."), frappe.ValidationError)

    signed_at = now_datetime()
    doc.review_completed = 1
    doc.reviewed_by = frappe.session.user
    doc.reviewer_name = _reviewer_name(frappe.session.user)
    doc.reviewed_at = signed_at
    doc.review_signature = _signature(signature)
    doc.review_notes = str(review_notes or "")[:MAX_REVIEW_NOTES_LENGTH]
    _append_review_audit(
        doc,
        "human_review_completed",
        {"reviewer": doc.reviewer_name, "revision": doc.revision},
    )
    doc.flags.allow_jha_review_mutation = True
    doc.save()
    return _serialize_review(doc)


@frappe.whitelist(methods=["POST"])
def acknowledge_jha_participant(
    jha_name: str,
    participant_row: str,
    signature: str,
    confirmation=0,
):
    _require_login()
    if not cint(confirmation):
        frappe.throw(
            _("The participant must confirm they have reviewed and understood the JHA."),
            frappe.ValidationError,
        )

    doc = _get_jha(jha_name, require_write=True)
    if doc.jha_status != "Ready for Team Review":
        frappe.throw(
            _("Participant sign-on is only available while the JHA is Ready for Team Review."),
            frappe.ValidationError,
        )
    if not cint(doc.get("review_completed")):
        frappe.throw(_("Complete the human review before participant sign-on."), frappe.ValidationError)

    row = next((item for item in (doc.participants or []) if item.name == participant_row), None)
    if not row:
        frappe.throw(_("JHA participant was not found."), frappe.DoesNotExistError)
    if not cint(row.present_for_discussion):
        frappe.throw(_("Only participants present for the discussion can sign on."), frappe.ValidationError)
    if cint(row.acknowledged):
        return _serialize_review(doc)

    acknowledged_at = now_datetime()
    row.acknowledged = 1
    row.acknowledged_at = acknowledged_at
    row.acknowledged_by_user = frappe.session.user
    row.acknowledgement_signature = _signature(signature)

    _append_review_audit(
        doc,
        "participant_acknowledged",
        {
            "participant_row": row.name,
            "participant_name": row.participant_name,
            "revision": doc.revision,
        },
    )

    if _all_required_participants_acknowledged(doc):
        doc.jha_status = "Signed"
        doc.signed_at = acknowledged_at
        doc.signed_by_user = frappe.session.user
        _append_review_audit(doc, "jha_signed", {"revision": doc.revision})

    doc.flags.allow_jha_review_mutation = True
    doc.save()
    return _serialize_review(doc)


@frappe.whitelist(methods=["POST"])
def reopen_changed_jha(jha_name: str, confirmation=0):
    _require_login()
    if not cint(confirmation):
        frappe.throw(
            _("Confirm that the JHA should be reopened for the changed work."),
            frappe.ValidationError,
        )

    doc = _get_jha(jha_name, require_write=True)
    if doc.jha_status != "Review Required - Work Changed":
        frappe.throw(_("This JHA does not require a work-change review."), frappe.ValidationError)

    old_revision = cint(doc.revision or 1)
    doc.revision = old_revision + 1
    doc.jha_status = "Incomplete - Actions Required"
    doc.review_completed = 0
    doc.reviewed_by = None
    doc.reviewer_name = None
    doc.reviewed_at = None
    doc.review_signature = None
    doc.signed_at = None
    doc.signed_by_user = None

    for row in doc.participants or []:
        row.acknowledged = 0
        row.acknowledged_at = None
        row.acknowledged_by_user = None
        row.acknowledgement_signature = None

    if hasattr(doc, "calculate_source_revision"):
        doc.source_revision = doc.calculate_source_revision()

    _append_review_audit(
        doc,
        "reopened_for_work_change",
        {"from_revision": old_revision, "to_revision": doc.revision},
    )
    doc.flags.allow_jha_review_mutation = True
    doc.save()
    return _serialize_review(doc)
