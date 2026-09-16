import frappe

from verto.api.mobile import voice_jha
from verto.api.mobile.voice_jha_progress import serialize_jha


REVIEW_STAGE_STATUSES = (
    "Review Required - Work Changed",
    "Signed",
)


def _review_stage_jha_name(work_summary: str) -> str:
    return (
        frappe.db.get_value(
            "Digital Job Hazard Analysis",
            {
                "work_summary": work_summary,
                "jha_status": ["in", list(REVIEW_STAGE_STATUSES)],
            },
            "name",
            order_by="modified desc",
        )
        or ""
    )


def _serialized_jha(name: str):
    if not name:
        return None
    doc = voice_jha._get_jha_doc(name)
    if hasattr(doc, "mark_review_required_if_source_changed"):
        changed = doc.mark_review_required_if_source_changed()
        if changed:
            doc.save(ignore_permissions=True)
    return serialize_jha(doc)


def _serialized_review_stage_jha(work_summary: str):
    return _serialized_jha(_review_stage_jha_name(work_summary))


@frappe.whitelist(methods=["GET"])
def get_voice_jha_bootstrap(work_summary: str):
    result = voice_jha.get_voice_jha_bootstrap(work_summary)
    existing = result.get("existing_jha") or {}
    if existing.get("name"):
        result["existing_jha"] = _serialized_jha(existing["name"])
        return result

    review_jha = _serialized_review_stage_jha(work_summary)
    if review_jha:
        result["existing_jha"] = review_jha
        result["prototype_stage"] = "human-review-signoff"
    return result


@frappe.whitelist(methods=["GET"])
def get_voice_jha_snapshot(jha_name: str):
    voice_jha._require_login()
    return serialize_jha(voice_jha._get_jha_doc(jha_name))


@frappe.whitelist(methods=["POST"])
def create_voice_jha_draft(work_summary: str):
    review_jha = _serialized_review_stage_jha(work_summary)
    if review_jha:
        review_jha["created"] = False
        return review_jha

    result = voice_jha.create_voice_jha_draft(work_summary)
    name = result.get("name") if isinstance(result, dict) else ""
    if not name:
        return result
    snapshot = _serialized_jha(name)
    snapshot["created"] = bool(result.get("created"))
    return snapshot
