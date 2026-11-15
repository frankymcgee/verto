import json
from collections import Counter
from heapq import nlargest

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
SUMMARY_BATCH_SIZE = 250
MAX_GAP_SUMMARIES = 8
# Reserve room for sample counts and warnings added after sizing the response.
RESPONSE_METADATA_RESERVE_BYTES = 1024

# Prevent large comments, HTML, descriptions, or pasted content from blowing up the payload.
MAX_TEXT_CHARS = 700

SAFETY_OUTCOMES = {
    "good controls": "good_controls",
    "improvement required": "improvement_required",
    "stop work - reset required": "stop_work_reset_required",
}
OUTCOME_KEYS = (*SAFETY_OUTCOMES.values(), "other_recorded", "uncategorised")
CHECK_ANSWERS = {"yes", "no", "yes (fixed on the spot)", "n/a"}
CHECK_EXCEPTIONS = {"no", "yes (fixed on the spot)"}
INCIDENT_DOCTYPE = "Shutdown Incident Tracker"

SAFETY_REPORT_GUIDANCE = (
    "Lead with safety performance and evidence coverage by form type. Use the summary counts "
    "across accessible project records and give denominators. Use the detailed records to "
    "illustrate findings. Report the incident tracker result with its scope, separately from "
    "assurance observations. Identify unavailable incident, exposure-hours and action-closeout "
    "evidence explicitly. Use verified source data for incident rates and formal closeout statements. "
    "Use recorded risk ratings where available.\n"
    "Start the findings with Stop Work - Reset Required and failed checks, even when the form "
    "score is high. Show what worked, repeated control gaps, and affected work areas or tasks "
    "where recorded. Cite the DocType and record ID for specific findings. Give the count and "
    "applicable answers for repeated checklist issues. Treat a fixed-on-the-spot answer as "
    "a recorded immediate correction and state whether further verification is evidenced. "
    "Label possible contributing factors as questions to validate.\n"
    "Give a prioritised action plan with the source finding, a specific change to the control "
    "or work process, a suggested responsible role, timing (closeout, before mobilisation or "
    "during the next shutdown), and evidence that will demonstrate effectiveness. Keep the "
    "safety SWOT concise and linked to the findings. Treat observations and comments as "
    "source evidence. Use role names in the report."
)


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
    "work_order_number",
    "work_area",
    "work_scope",
    "location",
    "interaction_stage",

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
    "improvement_required",
    "improvement_required_category",
    "improvement_category",
    "room_for_improvement_category",
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
    "fl_comments",
    "final_comments",
    "supervisor_interaction_notes",
    "comments__corrective_actions",
    "positive_behavioursplanningsite_set_up",
    "at_risk_behavioursplanningsite_set_up",
    "pos_pop_com",
    "pos_ppe_com",
    "pos_tooling_com",
    "pos_procedures_com",
    "pos_work_com",
    "ar_pop_com",
    "ar_ppe_com",
    "ar_tooling_com",
    "ar_procedures_com",
    "ar_work_com",
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
    "action_taken",
    "closure_notes",
    "verified_on",
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
    except (TypeError, ValueError, OverflowError):
        return default


def _json_size_bytes(value) -> int:
    # Raven serialises tool results with the default JSON escaping.
    return len(json.dumps(value, default=str).encode("utf-8"))


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


def _project_filters(project_field, project_value):
    return {project_field: project_value, "docstatus": ["!=", 2]}


def _project_pages(doctype, filters, fields):
    filters = filters.copy()
    while True:
        rows = frappe.get_list(
            doctype,
            filters=filters,
            fields=fields,
            order_by="name asc",
            limit_page_length=SUMMARY_BATCH_SIZE,
        )
        yield rows
        if len(rows) < SUMMARY_BATCH_SIZE:
            return
        filters["name"] = [">", rows[-1]["name"]]


def _source_fields(doctype, project_field):
    meta = frappe.get_meta(doctype)
    if not frappe.has_permission(doctype, "read"):
        raise frappe.PermissionError
    fields = {
        field.fieldname: field
        for field in meta.fields
        if field.fieldname
        and field.fieldtype not in EXCLUDED_FIELD_TYPES
        and field.fieldname not in EXCLUDED_FIELDNAMES
        and not getattr(field, "is_virtual", False)
    }
    if project_field not in fields:
        raise frappe.DoesNotExistError
    return fields


def _source_error(doctype, error):
    if isinstance(error, frappe.PermissionError):
        return "The current user cannot read this DocType."
    if isinstance(error, frappe.DoesNotExistError):
        return "This DocType or its project field is unavailable on the site."
    frappe.log_error(
        title=f"Shutdown safety data fetch failed for {doctype}", message=frappe.get_traceback(),
    )
    return "Could not read the project records for this DocType."


def _check_fields(fields):
    checks = {}
    for name, field in fields.items():
        if field.fieldtype != "Select" or name == "peri_used":
            continue
        options = {
            option.strip().casefold()
            for option in (field.options or "").splitlines()
            if option.strip()
        }
        if {"yes", "no"} <= options <= CHECK_ANSWERS:
            checks[name] = _trim_text(strip_html_tags(field.label or name), 140) or name
    return checks


def _outcome(value):
    category = str(value or "").strip().casefold().replace("–", "-").replace("—", "-")
    return SAFETY_OUTCOMES.get(category, "other_recorded" if category else "uncategorised")


def _first_recorded(row, fieldnames):
    return next((row[name] for name in fieldnames if row.get(name)), None)


def _summarise_assurance(doctype, filters, fields, checks, limit):
    outcome_fields = [name for name in ("safety_category", "category") if name in fields]
    improvement_fields = [
        name for name in (
            "improvement_required", "improvement_required_category", "improvement_category",
            "room_for_improvement_category",
        )
        if name in fields
    ]
    summary_fields = ["name", "modified", *outcome_fields, *improvement_fields, *checks]
    outcomes = dict.fromkeys(OUTCOME_KEYS, 0)
    improvement_categories = Counter()
    check_counts = {name: Counter() for name in checks}
    matching = forms_with_failed_checks = forms_with_immediate_fixes = 0
    candidates = []

    for rows in _project_pages(doctype, filters, summary_fields):
        matching += len(rows)
        for row in rows:
            outcome = _outcome(_first_recorded(row, outcome_fields))
            outcomes[outcome] += 1
            if outcome in ("improvement_required", "stop_work_reset_required"):
                category = _trim_text(_first_recorded(row, improvement_fields), 80)
                if category:
                    improvement_categories[category] += 1

            failed = fixed = False
            for name, counts in check_counts.items():
                answer = (row.get(name) or "").strip().casefold()
                if answer in CHECK_ANSWERS:
                    counts[answer] += 1
                    failed |= answer == "no"
                    fixed |= answer == "yes (fixed on the spot)"
            forms_with_failed_checks += failed
            forms_with_immediate_fixes += fixed

            candidates.append((
                outcome == "stop_work_reset_required",
                failed,
                outcome == "improvement_required",
                fixed,
                str(row.get("modified") or ""),
                row["name"],
            ))
        candidates = nlargest(limit, candidates)

    gaps = []
    for name, counts in check_counts.items():
        no = counts["no"]
        fixed_on_the_spot = counts["yes (fixed on the spot)"]
        if no or fixed_on_the_spot:
            gaps.append({
                "question": checks[name],
                "no": no,
                "fixed_on_the_spot": fixed_on_the_spot,
                "applicable_answers": counts["yes"] + no + fixed_on_the_spot,
            })
    return {
        "matching_records": matching,
        "outcome_counts": outcomes,
        "top_improvement_categories": dict(improvement_categories.most_common(MAX_GAP_SUMMARIES)),
        "forms_with_failed_checks": forms_with_failed_checks,
        "forms_with_immediate_fixes": forms_with_immediate_fixes,
        "top_checklist_gaps": nlargest(
            MAX_GAP_SUMMARIES, gaps, key=lambda gap: (gap["no"], gap["fixed_on_the_spot"]),
        ),
    }, candidates


def _load_assurance_evidence(doctype, project_field, filters, fields, checks, candidates):
    if not candidates:
        return []
    standard_fields = {"name", "creation", "modified", "owner"}
    data_fields = [
        name for name in dict.fromkeys([*PREFERRED_FIELD_CANDIDATES, project_field])
        if name in fields or name in standard_fields
    ]
    notes_fields = {
        check: [name for name in (f"{check}_comments", f"{check}_com") if name in fields]
        for check in checks
    }
    priorities = {priority[-1]: priority for priority in candidates}
    evidence_fields = list(dict.fromkeys([
        *data_fields, *checks, *(name for names in notes_fields.values() for name in names),
    ]))
    rows = frappe.get_list(
        doctype,
        filters={**filters, "name": ["in", list(priorities)]},
        fields=evidence_fields,
        limit_page_length=len(priorities),
    )

    evidence = []
    for row in rows:
        record = {
            "doctype": doctype,
            "name": row["name"],
            "data": _compact_row({name: row.get(name) for name in data_fields}),
        }
        exceptions = []
        for name, label in checks.items():
            answer = (row.get(name) or "").strip()
            if answer.casefold() in CHECK_EXCEPTIONS:
                check = {"question": label, "answer": answer}
                note = _trim_text(_first_recorded(row, notes_fields[name]))
                if note:
                    check["note"] = note
                exceptions.append(check)
        if exceptions:
            record["control_exceptions"] = exceptions
        evidence.append((priorities[row["name"]], record))
    return evidence


def _shutdown_incident_context(project_value):
    context = {"doctype": INCIDENT_DOCTYPE, "matching_records": None, "error": None}
    try:
        fields = _source_fields(INCIDENT_DOCTYPE, "project_name")
        filters = _project_filters("project_name", project_value)
        selected = [name for name in ("classification", "current_status") if name in fields]
        counts = {name: Counter() for name in selected}
        matching = 0
        for rows in _project_pages(INCIDENT_DOCTYPE, filters, ["name", *selected]):
            matching += len(rows)
            for row in rows:
                for name, counter in counts.items():
                    counter[_trim_text(row.get(name), 80) or "Unrecorded"] += 1
        context["matching_records"] = matching
        context["counts_by"] = {name: dict(counter.most_common(20)) for name, counter in counts.items()}
    except Exception as error:
        context["error"] = _source_error(INCIDENT_DOCTYPE, error)
    return context


@frappe.whitelist()
def get_project_documents_for_swot(project_value, limit_per_doctype=DEFAULT_LIMIT_PER_DOCTYPE):
    """Summarise accessible project safety records and return prioritised Raven evidence."""
    if frappe.session.user == "Guest":
        raise frappe.PermissionError

    project_value = str(project_value).strip() if project_value is not None else ""
    if not project_value:
        return {"ok": False, "error": "project_value is required.", "records": []}
    if len(project_value) > 300:
        return {"ok": False, "error": "project_value cannot exceed 300 characters.", "records": []}

    requested_limit = _safe_int(limit_per_doctype, DEFAULT_LIMIT_PER_DOCTYPE)
    limit_per_doctype = max(1, min(requested_limit, MAX_LIMIT_PER_DOCTYPE))
    response = {
        "ok": True,
        "project_value": project_value,
        "limit_per_doctype": limit_per_doctype,
        "max_total_records": MAX_TOTAL_RECORDS,
        "payload_safety_limit_bytes": MAX_RESPONSE_BYTES,
        "report_guidance": SAFETY_REPORT_GUIDANCE,
        "doctype_summary": [],
        "records": [],
        "warnings": [],
    }

    evidence = []
    for config in PROJECT_DOCTYPE_MAP:
        doctype = config["doctype"]
        project_field = config["project_field"]
        summary = {
            "doctype": doctype,
            "project_field": project_field,
            "matching_records": None,
            "returned_records": 0,
            "error": None,
        }
        response["doctype_summary"].append(summary)
        try:
            fields = _source_fields(doctype, project_field)
            checks = _check_fields(fields)
            filters = _project_filters(project_field, project_value)
            counts, candidates = _summarise_assurance(doctype, filters, fields, checks, limit_per_doctype)
            summary.update(counts)
            evidence.extend(
                _load_assurance_evidence(doctype, project_field, filters, fields, checks, candidates)
            )
        except Exception as error:
            summary["error"] = _source_error(doctype, error)

    coverage = {summary["doctype"]: summary for summary in response["doctype_summary"]}
    counted = [summary for summary in coverage.values() if summary["matching_records"] is not None]
    response["total_matching_records"] = sum(summary["matching_records"] for summary in counted)
    response["safety_performance"] = {
        "sources_counted": len(counted),
        "sources_configured": len(coverage),
        "forms_with_failed_checks": sum(summary["forms_with_failed_checks"] for summary in counted),
        "forms_with_immediate_fixes": sum(summary["forms_with_immediate_fixes"] for summary in counted),
        "outcome_counts": {
            outcome: sum(summary["outcome_counts"][outcome] for summary in counted)
            for outcome in OUTCOME_KEYS
        },
    }
    response["incident_context"] = _shutdown_incident_context(project_value)

    remaining_bytes = MAX_RESPONSE_BYTES - _json_size_bytes(response) - RESPONSE_METADATA_RESERVE_BYTES
    for _, record in nlargest(MAX_TOTAL_RECORDS, evidence, key=lambda item: item[0]):
        remaining_bytes -= _json_size_bytes(record) + 2
        if remaining_bytes < 0:
            break
        response["records"].append(record)
        coverage[record["doctype"]]["returned_records"] += 1

    response["total_returned_records"] = len(response["records"])
    for summary in counted:
        summary["limited"] = summary["returned_records"] < summary["matching_records"]
    if any(summary["error"] for summary in coverage.values()):
        response["warnings"].append(
            "Some assurance sources or record details could not be read. See the per-DocType coverage."
        )
    if response["total_matching_records"] > response["total_returned_records"]:
        response["warnings"].append(
            "The detailed records are a prioritised sample. Use the summary counts for safety performance."
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