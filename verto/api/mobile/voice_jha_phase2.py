import frappe

from verto.api.mobile import voice_jha


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


def _serialized_review_stage_jha(work_summary: str):
    name = _review_stage_jha_name(work_summary)
    if not name:
        return None
    doc = voice_jha._get_jha_doc(name)
    if hasattr(doc, "mark_review_required_if_source_changed"):
        changed = doc.mark_review_required_if_source_changed()
        if changed:
            doc.save(ignore_permissions=True)
    return voice_jha._serialize_jha(doc)


@frappe.whitelist(methods=["GET"])
def get_voice_jha_bootstrap(work_summary: str):
    result = voice_jha.get_voice_jha_bootstrap(work_summary)
    if result.get("existing_jha"):
        return result

    review_jha = _serialized_review_stage_jha(work_summary)
    if review_jha:
        result["existing_jha"] = review_jha
        result["prototype_stage"] = "human-review-signoff"
    return result


@frappe.whitelist(methods=["POST"])
def create_voice_jha_draft(work_summary: str):
    review_jha = _serialized_review_stage_jha(work_summary)
    if review_jha:
        review_jha["created"] = False
        return review_jha
    return voice_jha.create_voice_jha_draft(work_summary)
