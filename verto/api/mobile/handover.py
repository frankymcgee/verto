import re
from typing import Any

import frappe
from frappe import _


# Fallback order only. When the frontend passes handover_base / handover_doctype,
# that selected DocType is used first so Safety Handover and Lead Safety Handover
# do not get mixed up.
HANDOVER_DOCTYPE_CANDIDATES = [
    "Safety Handover",
    "Lead Safety Handover",
    "Project Handover",
    "Handover",
]

PROJECT_LINK_FIELD_CANDIDATES = [
    "project",
    "custom_project",
    "project_name",
    "custom_project_name",
    "project_scope_name",
    "custom_project_scope_name",
]

HANDOVER_BASE_TO_DOCTYPE = {
    "lead-safety-handover": "Lead Safety Handover",
    "lead_safety_handover": "Lead Safety Handover",
    "safety-handover": "Safety Handover",
    "safety_handover": "Safety Handover",
    "project-handover": "Project Handover",
    "project_handover": "Project Handover",
}


def _slugify(value: str) -> str:
    """Convert a DocType name to the Verto mobile route slug style."""
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def _doctype_exists(doctype: str) -> bool:
    return bool(doctype and frappe.db.exists("DocType", doctype))


def _get_meta(doctype: str):
    if not _doctype_exists(doctype):
        return None

    return frappe.get_meta(doctype)


def _meta_has_field(meta, fieldname: str) -> bool:
    return bool(meta and meta.has_field(fieldname))


def _get_matching_project_fields(meta) -> list[str]:
    return [
        fieldname
        for fieldname in PROJECT_LINK_FIELD_CANDIDATES
        if _meta_has_field(meta, fieldname)
    ]


def _normalise_candidates(*values: str | None) -> list[str]:
    candidates: list[str] = []

    for value in values:
        if value is None:
            continue

        value = str(value).strip()

        if value and value not in candidates:
            candidates.append(value)

    return candidates


def _normalise_handover_doctype(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = str(value).strip()

    if not cleaned:
        return None

    lower_value = cleaned.lower()

    if lower_value in {"lead", "lead_safety", "lead-safety", "lead safety"}:
        return "Lead Safety Handover"

    if lower_value in {"safety", "safety_handover", "safety-handover", "safety handover"}:
        return "Safety Handover"

    if lower_value in {"project", "project_handover", "project-handover", "project handover"}:
        return "Project Handover"

    # Already a real DocType name.
    if _doctype_exists(cleaned):
        return cleaned

    # Route slug style, e.g. lead-safety-handover.
    for doctype in HANDOVER_DOCTYPE_CANDIDATES:
        if lower_value == _slugify(doctype):
            return doctype

    return cleaned


def _infer_handover_doctype_from_base(handover_base: str | None) -> str | None:
    value = str(handover_base or "").strip().lower()

    if not value:
        return None

    for key, doctype in HANDOVER_BASE_TO_DOCTYPE.items():
        if key in value:
            return doctype

    return None


def _get_candidate_doctypes(
    handover_doctype: str | None = None,
    handover_base: str | None = None,
    handover_type: str | None = None,
) -> list[str]:
    selected = (
        _normalise_handover_doctype(handover_doctype)
        or _normalise_handover_doctype(handover_type)
        or _infer_handover_doctype_from_base(handover_base)
    )

    candidates: list[str] = []

    if selected:
        candidates.append(selected)

    for doctype in HANDOVER_DOCTYPE_CANDIDATES:
        if doctype not in candidates:
            candidates.append(doctype)

    return candidates


def _resolve_mobile_doctype(doctype: str) -> str:
    """
    Try to find a configured mobile doctype slug for the target DocType.

    The project has evolved a few times, so this checks common naming patterns.
    If no config DocType exists or no config row is found, it falls back to the
    standard Verto route slug, e.g. "Safety Handover" -> "safety-handover".
    """
    config_doctype_candidates = [
        "Mobile DocType",
        "Mobile Doctype",
        "Mobile Form",
        "Verto Mobile DocType",
        "Verto Mobile Form",
    ]

    target_field_candidates = [
        "doctype",
        "document_type",
        "ref_doctype",
        "dt",
        "target_doctype",
    ]

    slug_field_candidates = [
        "mobile_doctype",
        "route",
        "slug",
        "name",
    ]

    for config_doctype in config_doctype_candidates:
        if not _doctype_exists(config_doctype):
            continue

        meta = frappe.get_meta(config_doctype)

        for target_field in target_field_candidates:
            if not meta.has_field(target_field):
                continue

            config_name = frappe.db.get_value(
                config_doctype,
                {target_field: doctype},
                "name",
            )

            if not config_name:
                continue

            for slug_field in slug_field_candidates:
                if slug_field == "name":
                    value = config_name
                elif meta.has_field(slug_field):
                    value = frappe.db.get_value(config_doctype, config_name, slug_field)
                else:
                    value = None

                if value:
                    return _slugify(value)

    return _slugify(doctype)


def _find_handover_record(doctype: str, project_values: list[str]) -> str | None:
    meta = _get_meta(doctype)

    if not meta:
        return None

    project_fields = _get_matching_project_fields(meta)

    for fieldname in project_fields:
        for value in project_values:
            name = frappe.db.get_value(
                doctype,
                {fieldname: value},
                "name",
                order_by="modified desc",
            )

            if name:
                return name

    # Fallback for doctypes that use title/name fields rather than a project link.
    for title_field in ["title", "subject", "handover_name"]:
        if not _meta_has_field(meta, title_field):
            continue

        for value in project_values:
            name = frappe.db.get_value(
                doctype,
                {title_field: value},
                "name",
                order_by="modified desc",
            )

            if name:
                return name

    return None


def _create_handover_record(doctype: str, project_values: list[str]) -> str:
    meta = _get_meta(doctype)

    if not meta:
        frappe.throw(_("Handover DocType {0} does not exist.").format(doctype))

    if not frappe.has_permission(doctype, ptype="create"):
        frappe.throw(_("You do not have permission to create {0}.").format(doctype), frappe.PermissionError)

    project_value = project_values[0] if project_values else ""
    doc = frappe.new_doc(doctype)

    for fieldname in _get_matching_project_fields(meta):
        doc.set(fieldname, project_value)
        break

    if _meta_has_field(meta, "title") and not doc.get("title"):
        doc.set("title", project_values[1] if len(project_values) > 1 else project_value)

    doc.insert(ignore_permissions=False)

    return doc.name


@frappe.whitelist(methods=["POST"])
def get_or_create_project_handover(
    project: str | None = None,
    project_name: str | None = None,
    scope_name: str | None = None,
    handover_doctype: str | None = None,
    handover_base: str | None = None,
    handover_type: str | None = None,
) -> dict[str, Any]:
    """
    Resolve the existing handover record for a project and return the Verto edit route.

    The native Home page now passes the same handover_base concept used by the old
    HTML block. If handover_base points at /app/lead-safety-handover, this opens
    Lead Safety Handover. If it points at /app/safety-handover, this opens Safety
    Handover.

    Expected frontend route:
        /verto-mobile/edit/<mobile_doctype>/<docname>
    """
    project_values = _normalise_candidates(project, project_name, scope_name)

    if not project_values:
        frappe.throw(_("Project is required to open the handover."))

    candidate_doctypes = _get_candidate_doctypes(
        handover_doctype=handover_doctype,
        handover_base=handover_base,
        handover_type=handover_type,
    )

    found_doctype = None
    found_name = None

    # If a doctype was explicitly selected by handover_base or handover_doctype,
    # try it first and do not accidentally open the other handover type just
    # because that record exists.
    requested_doctype = candidate_doctypes[0] if candidate_doctypes else None

    if requested_doctype and _doctype_exists(requested_doctype):
        found_doctype = requested_doctype
        found_name = _find_handover_record(requested_doctype, project_values)

        if not found_name:
            found_name = _create_handover_record(requested_doctype, project_values)

    if not found_doctype or not found_name:
        for doctype in candidate_doctypes:
            if not _doctype_exists(doctype):
                continue

            name = _find_handover_record(doctype, project_values)

            if name:
                found_doctype = doctype
                found_name = name
                break

    if not found_doctype or not found_name:
        for doctype in candidate_doctypes:
            if _doctype_exists(doctype):
                found_doctype = doctype
                found_name = _create_handover_record(doctype, project_values)
                break

    if not found_doctype or not found_name:
        frappe.throw(_("No project handover DocType is configured or available."))

    if not frappe.has_permission(found_doctype, doc=found_name, ptype="read"):
        frappe.throw(_("You do not have permission to open this handover."), frappe.PermissionError)

    mobile_doctype = _resolve_mobile_doctype(found_doctype)

    return {
        "doctype": found_doctype,
        "mobile_doctype": mobile_doctype,
        "name": found_name,
        "route": f"/edit/{mobile_doctype}/{found_name}",
        "created": False,
        "requested_doctype": requested_doctype,
        "handover_base": handover_base,
    }
