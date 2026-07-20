import json
import frappe
from frappe.utils import cint, strip_html_tags


PROJECT_DOCTYPE_MAP = [
    {"doctype": "CCV - Confined Space", "project_field": "project_name"},
    {"doctype": "CCV - Contact with Electricity", "project_field": "project_name"},
    {"doctype": "CCV - Dropped Objects", "project_field": "project_name"},
    {"doctype": "CCV - Entanglement and Crushing", "project_field": "project_name"},
    {"doctype": "CCV - Fall From Height", "project_field": "project_name"},
    {"doctype": "CCV - Hot Works", "project_field": "project_name"},
    {"doctype": "CCV - Lifting Operations", "project_field": "project_name"},
    {"doctype": "CCV - Uncontrolled Release of Energy", "project_field": "project_name"},
    {"doctype": "CCV - Vehicles and Mobile Equipment", "project_field": "project_name"},
    {"doctype": "CCV - Working Near Water", "project_field": "project_name"},
    {"doctype": "Commitment Interaction", "project_field": "project_name"},
    {"doctype": "Field Interaction", "project_field": "project_name"},
    {"doctype": "Job Hazard Analysis Review", "project_field": "project_name"},
    {"doctype": "Supervisor BATB", "project_field": "project_name"},
    {"doctype": "Workplace Inspection", "project_field": "project_name"},
]


# Keep safely below OpenAI's 512 KB combined tool output limit.
# This leaves room for request overhead and any other tool output submitted in the same run.
MAX_RESPONSE_BYTES = 430 * 1024

# Prevent a single project with thousands of records from flooding the AI context.
DEFAULT_LIMIT_PER_DOCTYPE = 25
MAX_LIMIT_PER_DOCTYPE = 75
MAX_TOTAL_RECORDS = 300

# Prevent large comments, HTML, descriptions, or pasted content from blowing up the payload.
MAX_TEXT_CHARS = 700


# Fields that are usually useful for SWOT/safety analysis.
# The function will only request fields that actually exist on the DocType.
PREFERRED_FIELD_CANDIDATES = [
    "name",
    "creation",
    "modified",
    "owner",

    # Project / scope fields
    "project_name",
    "project",
    "link_project",
    "project_scope_name",
    "link_task",
    "task",
    "work_order",

    # People / contractor fields
    "contractor",
    "contractor_name",
    "supervisor",
    "supervisor_name",
    "employee",
    "employee_name",
    "reported_by",
    "completed_by",
    "person_responsible",

    # Date / time / shift
    "date",
    "inspection_date",
    "review_date",
    "date_and_time",
    "time",
    "shift",
    "shift_type",

    # Safety / compliance categories
    "safety_category",
    "improvement_required_category",
    "improvement_category",
    "classification",
    "category",
    "type",
    "status",
    "current_status",
    "risk_rating",
    "consequence",
    "likelihood",
    "compliance_percentage",
    "score",
    "result",

    # Short title fields
    "title",
    "subject",
    "form_name",

    # Useful narrative fields
    "description",
    "comments",
    "comment",
    "observation",
    "observations",
    "findings",
    "summary",
    "details",
    "notes",
    "action_required",
    "actions_required",
    "corrective_action",
    "corrective_actions",
    "recommendation",
    "recommendations",
    "positive_observations",
    "areas_for_improvement",
]


# Field types that should never be returned to the AI as part of this tool output.
# These are commonly large, binary-ish, repetitive, or not useful for SWOT.
EXCLUDED_FIELD_TYPES = {
    "Table",
    "Table MultiSelect",
    "Attach",
    "Attach Image",
    "Image",
    "Signature",
    "Barcode",
    "Code",
    "HTML",
    "Button",
    "Section Break",
    "Column Break",
    "Tab Break",
    "Fold",
    "Heading",
}


# Field names that are usually noisy or can contain large/base64/HTML-like content.
EXCLUDED_FIELDNAMES = {
    "_assign",
    "_comments",
    "_liked_by",
    "_seen",
    "amended_from",
    "docstatus",
    "idx",
    "image",
    "images",
    "photo",
    "photos",
    "signature",
    "client_signature",
    "employee_signature",
    "supervisor_signature",
    "attachment",
    "attachments",
}


def _safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def _json_size_bytes(value) -> int:
    return len(json.dumps(value, default=str, ensure_ascii=False).encode("utf-8"))


def _trim_text(value, max_chars=MAX_TEXT_CHARS):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # Basic cleanup so the AI receives readable text rather than huge whitespace blocks.
    text = " ".join(text.split())

    if len(text) > max_chars:
        return text[:max_chars] + "... [truncated]"

    return text


def _get_existing_compact_fields(doctype, project_field):
    """
    Return a safe list of fields that exist on the DocType and are useful for AI analysis.
    Avoids child tables, signatures, attachments, images, HTML/code, and other noisy fields.
    """

    meta = frappe.get_meta(doctype)

    valid_fieldnames = {
        df.fieldname
        for df in meta.fields
        if df.fieldname
        and df.fieldtype not in EXCLUDED_FIELD_TYPES
        and df.fieldname not in EXCLUDED_FIELDNAMES
    }

    selected = []

    for fieldname in PREFERRED_FIELD_CANDIDATES:
        if fieldname == "name":
            selected.append("name")
        elif fieldname in valid_fieldnames:
            selected.append(fieldname)

    # Ensure the project filter field is returned where possible.
    if project_field and project_field in valid_fieldnames and project_field not in selected:
        selected.append(project_field)

    # Always keep these document timestamps if available.
    for standard_field in ["creation", "modified", "owner"]:
        if standard_field not in selected:
            selected.append(standard_field)

    # Remove duplicates while preserving order.
    final_fields = []
    for fieldname in selected:
        if fieldname not in final_fields:
            final_fields.append(fieldname)

    return final_fields or ["name"]


def _compact_row(row):
    """
    Convert a Frappe row into a small dict.
    Trims long text fields and drops empty values.
    """

    compact = {}

    for key, value in dict(row).items():
        if value is None or value == "":
            continue

        # Keep common numeric/date/status fields as-is.
        if isinstance(value, (int, float, bool)):
            compact[key] = value
            continue

        trimmed = _trim_text(value)

        if trimmed is not None:
            compact[key] = trimmed

    return compact


def _is_response_too_large(response):
    return _json_size_bytes(response) >= MAX_RESPONSE_BYTES


@frappe.whitelist(allow_guest=True)
def get_project_documents_for_swot(project_value, limit_per_doctype=DEFAULT_LIMIT_PER_DOCTYPE):
    """
    Return compact records across configured DocTypes where the project field matches project_value.

    This version is designed for AI/Raven SWOT analysis and avoids returning full documents via
    doc.as_dict(), because full documents can exceed OpenAI's 512 KB combined tool output limit.

    Key safeguards:
    - Does not load full DocTypes with frappe.get_doc().
    - Does not return child tables, signatures, images, attachments, or large HTML/code fields.
    - Trims long comments/descriptions.
    - Caps records per DocType and total records.
    - Stops early if the response approaches the safe payload size.
    """

    project_value = _trim_text(project_value, 300)

    if not project_value:
        return {
            "ok": False,
            "error": "project_value is required.",
            "records": [],
        }

    requested_limit = _safe_int(limit_per_doctype, DEFAULT_LIMIT_PER_DOCTYPE)
    limit_per_doctype = max(1, min(requested_limit, MAX_LIMIT_PER_DOCTYPE))

    response = {
        "ok": True,
        "project_value": project_value,
        "limit_per_doctype": limit_per_doctype,
        "max_total_records": MAX_TOTAL_RECORDS,
        "payload_safety_limit_bytes": MAX_RESPONSE_BYTES,
        "total_matching_records": 0,
        "total_returned_records": 0,
        "doctype_summary": [],
        "records": [],
        "warnings": [],
    }

    total_returned = 0

    for config in PROJECT_DOCTYPE_MAP:
        if total_returned >= MAX_TOTAL_RECORDS:
            response["warnings"].append(
                f"Stopped after {MAX_TOTAL_RECORDS} returned records to keep the AI tool output compact."
            )
            break

        doctype = config["doctype"]
        project_field = config["project_field"]

        doctype_summary = {
            "doctype": doctype,
            "project_field": project_field,
            "matching_records": 0,
            "returned_records": 0,
            "error": None,
        }

        try:
            meta = frappe.get_meta(doctype)

            if not meta.has_field(project_field):
                doctype_summary["error"] = f"Project field '{project_field}' does not exist on {doctype}."
                response["doctype_summary"].append(doctype_summary)
                continue

            filters = {project_field: project_value}

            matching_count = frappe.db.count(doctype, filters=filters)
            doctype_summary["matching_records"] = matching_count
            response["total_matching_records"] += matching_count

            if matching_count == 0:
                response["doctype_summary"].append(doctype_summary)
                continue

            fields = _get_existing_compact_fields(doctype, project_field)

            remaining_total_capacity = MAX_TOTAL_RECORDS - total_returned
            query_limit = min(limit_per_doctype, remaining_total_capacity)

            rows = frappe.get_all(
                doctype,
                filters=filters,
                fields=fields,
                order_by="modified desc",
                limit_page_length=query_limit,
            )

            for row in rows:
                compact_record = {
                    "doctype": doctype,
                    "name": row.get("name"),
                    "data": _compact_row(row),
                }

                response["records"].append(compact_record)
                total_returned += 1
                doctype_summary["returned_records"] += 1
                response["total_returned_records"] = total_returned

                if _is_response_too_large(response):
                    # Remove the record that pushed the response over the safe limit.
                    response["records"].pop()
                    total_returned -= 1
                    doctype_summary["returned_records"] -= 1
                    response["total_returned_records"] = total_returned

                    response["warnings"].append(
                        "Stopped early because the compact SWOT payload approached the OpenAI tool output size limit."
                    )
                    response["doctype_summary"].append(doctype_summary)
                    return response

            if matching_count > doctype_summary["returned_records"]:
                doctype_summary["limited"] = True
                doctype_summary["message"] = (
                    f"Returned {doctype_summary['returned_records']} of {matching_count} matching records "
                    "for this DocType."
                )

        except Exception as e:
            doctype_summary["error"] = str(e)

            frappe.log_error(
                title=f"SWOT document fetch failed for {doctype}",
                message=frappe.get_traceback(),
            )

        response["doctype_summary"].append(doctype_summary)

    if response["total_matching_records"] > response["total_returned_records"]:
        response["warnings"].append(
            "The result is intentionally summarised/limited for AI analysis. "
            "Use a narrower project, smaller limit, or a separate export function if raw records are required."
        )

    return response

@frappe.whitelist()
def get_weekly_summaries(project_name, limit=12):
    """
    Fetch Weekly Summary records for Raven analysis.

    Args:
        project_name (str): Exact value stored in Weekly Summary.project_name.
        limit (int): Maximum number of records to return.

    Returns:
        dict: Structured Weekly Summary information.
    """

    project_name = (project_name or "").strip()
    limit = min(max(cint(limit) or 12, 1), 52)

    if not project_name:
        return {
            "success": False,
            "message": "A project_name must be provided.",
            "project_name": None,
            "record_count": 0,
            "weekly_summaries": [],
        }

    if not frappe.db.exists("DocType", "Weekly Summary"):
        return {
            "success": False,
            "message": "The Weekly Summary DocType does not exist.",
            "project_name": project_name,
            "record_count": 0,
            "weekly_summaries": [],
        }

    if not frappe.has_permission("Weekly Summary", "read"):
        return {
            "success": False,
            "message": (
                "The current user does not have permission to read "
                "Weekly Summary records."
            ),
            "project_name": project_name,
            "record_count": 0,
            "weekly_summaries": [],
        }

    def clean_text(value):
        """Convert Text Editor HTML into cleaner text for Raven."""

        if not value:
            return ""

        value = str(value)

        replacements = {
            "<br>": "\n",
            "<br/>": "\n",
            "<br />": "\n",
            "</p>": "\n",
            "</div>": "\n",
            "</li>": "\n",
        }

        for old_value, new_value in replacements.items():
            value = value.replace(old_value, new_value)

        value = strip_html_tags(value)

        lines = [
            line.strip()
            for line in value.splitlines()
            if line.strip()
        ]

        return "\n".join(lines)

    def serialize_value(value, fieldtype=None):
        """Make field values safe and useful for Raven."""

        if value is None:
            return ""

        if fieldtype in (
            "Text Editor",
            "Text",
            "Small Text",
            "Long Text",
            "Markdown Editor",
        ):
            return clean_text(value)

        if hasattr(value, "isoformat"):
            return value.isoformat()

        return value

    records = frappe.get_list(
        "Weekly Summary",
        filters={
            "project_name": project_name,
        },
        fields=[
            "name",
            "creation",
            "modified",
        ],
        order_by="creation desc",
        limit_page_length=limit,
    )

    weekly_summaries = []

    kpi_meta = frappe.get_meta("Weekly Summary KPIs")

    excluded_kpi_fields = {
        "name",
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "parent",
        "parentfield",
        "parenttype",
    }

    ignored_fieldtypes = {
        "Section Break",
        "Column Break",
        "Tab Break",
        "HTML",
        "Button",
        "Table",
        "Table MultiSelect",
    }

    kpi_fields = [
        field
        for field in kpi_meta.fields
        if field.fieldname
        and field.fieldname not in excluded_kpi_fields
        and field.fieldtype not in ignored_fieldtypes
    ]

    for record in records:
        doc = frappe.get_doc("Weekly Summary", record.name)
        doc.check_permission("read")

        kpis = []

        for row in doc.weekly_kpis or []:
            kpi = {}

            for field in kpi_fields:
                value = row.get(field.fieldname)

                if value not in (None, ""):
                    kpi[field.fieldname] = serialize_value(
                        value,
                        field.fieldtype,
                    )

            if kpi:
                kpi["row_number"] = row.idx
                kpis.append(kpi)

        weekly_summaries.append({
            "name": doc.name,
            "created_on": (
                doc.creation.isoformat()
                if doc.creation
                else None
            ),
            "modified_on": (
                doc.modified.isoformat()
                if doc.modified
                else None
            ),
            "project": {
                "project_name": doc.project_name,
                "project_id": doc.link_project,
            },
            "work_information": {
                "scope_or_work_order": doc.scope_or_wo,
                "linked_task": doc.link_task,
                "work_scope": doc.work_scope,
                "work_order_number": doc.work_order_number,
                "work_area": doc.work_area,
            },
            "summary_information": {
                "weekly_summary": clean_text(
                    doc.weekly_summary
                ),
                "key_deliverables": clean_text(
                    doc.key_deliverables_for_the_week
                ),
                "documentation_updates": clean_text(
                    doc.documentation_updates
                ),
                "critical_risks_and_observations": clean_text(
                    doc.critital_risks_observations
                ),
                "comments": clean_text(doc.fl_comments),
            },
            "performance_metrics_and_kpis": kpis,
        })

    return {
        "success": True,
        "message": (
            f"Found {len(weekly_summaries)} Weekly Summary records "
            f"for project '{project_name}'. Use these records to identify "
            "progress, completed deliverables, documentation changes, "
            "performance trends, recurring risks, observations and areas "
            "requiring follow-up."
        ),
        "project_name": project_name,
        "record_count": len(weekly_summaries),
        "records_ordered": "newest_to_oldest",
        "weekly_summaries": weekly_summaries,
    }