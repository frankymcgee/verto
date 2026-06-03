import json
import frappe


@frappe.whitelist()
def get_shutdown_safety_dashboard_context(project_scope_name=None):
    """
    Returns structured Shutdown Safety Metrics dashboard data for PERI/Raven AI.

    Only filter:
    - project_scope_name

    If project_scope_name is blank, all project scopes are analysed.
    """

    project_scope_name = clean_optional_value(project_scope_name)

    payload = {
        "dashboard": "Shutdown Safety Metrics",
        "workbook": "HL Safety Metrics",
        "filters": {
            "project_scope_name": project_scope_name,
        },
        "charts": {
            "compliance_trend": get_compliance_trend(project_scope_name),
            "work_area_compliance": get_work_area_compliance(project_scope_name),
            "contractor_compliance": get_contractor_compliance(project_scope_name),
            "areas_for_improvement": get_areas_for_improvement(project_scope_name),
            "form_compliance": get_form_compliance_cards(project_scope_name),
            "critical_control_verification": get_ccv_compliance_cards(project_scope_name),
            "positive_and_at_risk_behaviours": get_positive_and_at_risk_behaviours(project_scope_name),
        },
    }

    payload["peri_prompt"] = build_peri_dashboard_prompt(payload)

    return payload


def clean_optional_value(value):
    if value in [None, "", "null", "undefined", "None"]:
        return None

    return value


def get_project_scope_condition(project_scope_name=None):
    if not project_scope_name:
        return "", {}

    return "WHERE t.project_scope_name = %(project_scope_name)s", {
        "project_scope_name": project_scope_name,
    }


def append_condition(where_clause, condition):
    if where_clause:
        return where_clause + " AND " + condition

    return "WHERE " + condition


def run_sql(sql, values=None):
    return frappe.db.sql(sql, values or {}, as_dict=True)


def get_compliance_trend(project_scope_name=None):
    where_clause, values = get_project_scope_condition(project_scope_name)

    where_clause = append_condition(
        where_clause,
        "sm.date_submitted IS NOT NULL AND sm.compliance_percentage IS NOT NULL",
    )

    sql = f"""
        SELECT
            DATE(sm.date_submitted) AS date_submitted,
            ROUND(MAX(sm.compliance_percentage), 2) AS max_compliance_percentage,
            ROUND(MIN(sm.compliance_percentage), 2) AS min_compliance_percentage,
            ROUND(AVG(sm.compliance_percentage), 2) AS avg_compliance_percentage,
            COUNT(*) AS record_count
        FROM `tabSafety Metrics` sm
        LEFT JOIN `tabTask` t ON t.name = sm.parent
        {where_clause}
        GROUP BY DATE(sm.date_submitted)
        ORDER BY DATE(sm.date_submitted) ASC
        LIMIT 100
    """

    return run_sql(sql, values)


def get_work_area_compliance(project_scope_name=None):
    where_clause, values = get_project_scope_condition(project_scope_name)

    where_clause = append_condition(
        where_clause,
        "sm.compliance_percentage IS NOT NULL",
    )

    sql = f"""
        SELECT
            COALESCE(NULLIF(t.parent_task_name, ''), t.name) AS work_location,
            ROUND(AVG(sm.compliance_percentage), 2) AS avg_compliance_percentage,
            COUNT(*) AS record_count
        FROM `tabSafety Metrics` sm
        LEFT JOIN `tabTask` t ON t.name = sm.parent
        {where_clause}
        GROUP BY COALESCE(NULLIF(t.parent_task_name, ''), t.name)
        ORDER BY avg_compliance_percentage ASC
        LIMIT 100
    """

    return run_sql(sql, values)


def get_contractor_compliance(project_scope_name=None):
    where_clause, values = get_project_scope_condition(project_scope_name)

    where_clause = append_condition(
        where_clause,
        """
        sm.compliance_percentage IS NOT NULL
        AND IFNULL(sm.contractor, '') != ''
        """,
    )

    sql = f"""
        SELECT
            sm.contractor AS contractor,
            ROUND(AVG(sm.compliance_percentage), 2) AS avg_compliance_percentage,
            COUNT(*) AS record_count
        FROM `tabSafety Metrics` sm
        LEFT JOIN `tabTask` t ON t.name = sm.parent
        {where_clause}
        GROUP BY sm.contractor
        ORDER BY avg_compliance_percentage ASC
        LIMIT 100
    """

    return run_sql(sql, values)


def get_areas_for_improvement(project_scope_name=None):
    where_clause, values = get_project_scope_condition(project_scope_name)

    where_clause = append_condition(
        where_clause,
        """
        IFNULL(sm.safety_category, '') NOT IN ('', 'Good Controls')
        AND IFNULL(sm.improvement_required, '') != ''
        """,
    )

    sql = f"""
        SELECT
            sm.improvement_required AS improvement_required,
            COUNT(*) AS count
        FROM `tabSafety Metrics` sm
        LEFT JOIN `tabTask` t ON t.name = sm.parent
        {where_clause}
        GROUP BY sm.improvement_required
        ORDER BY count DESC
        LIMIT 100
    """

    return run_sql(sql, values)


def get_form_compliance_cards(project_scope_name=None):
    forms = [
        {
            "key": "batb_compliance",
            "title": "BATB Compliance",
            "form_submitted": "Supervisor BATB",
        },
        {
            "key": "fld_compliance",
            "title": "FLD Compliance",
            "form_submitted": "Field Interaction",
        },
        {
            "key": "cmi_compliance",
            "title": "CMI Compliance",
            "form_submitted": "Commitment Interaction",
        },
        {
            "key": "wpi_compliance",
            "title": "WPI Compliance",
            "form_submitted": "Workplace Inspection",
        },
        {
            "key": "jha_compliance",
            "title": "JHA Compliance",
            "form_submitted": "Job Hazard Analysis Review",
        },
    ]

    data = []

    for form in forms:
        row = get_average_compliance_for_form(
            title=form["title"],
            form_submitted=form["form_submitted"],
            project_scope_name=project_scope_name,
        )

        row["key"] = form["key"]
        data.append(row)

    return data


def get_average_compliance_for_form(title, form_submitted, project_scope_name=None):
    where_clause, values = get_project_scope_condition(project_scope_name)

    values["form_submitted"] = form_submitted
    values["title"] = title

    where_clause = append_condition(
        where_clause,
        """
        sm.form_submitted = %(form_submitted)s
        AND sm.compliance_percentage IS NOT NULL
        """,
    )

    sql = f"""
        SELECT
            %(title)s AS title,
            %(form_submitted)s AS form_submitted,
            ROUND(AVG(sm.compliance_percentage), 2) AS avg_compliance_percentage,
            COUNT(*) AS record_count
        FROM `tabSafety Metrics` sm
        LEFT JOIN `tabTask` t ON t.name = sm.parent
        {where_clause}
    """

    rows = run_sql(sql, values)

    if rows:
        return rows[0]

    return {
        "title": title,
        "form_submitted": form_submitted,
        "avg_compliance_percentage": None,
        "record_count": 0,
    }


def get_ccv_compliance_cards(project_scope_name=None):
    ccv_forms = [
        {
            "key": "confined_space",
            "title": "Confined Space",
            "starts_with": "CCV - Confined",
        },
        {
            "key": "contact_with_electricity",
            "title": "Contact with Electricity",
            "starts_with": "CCV - Contact with Electricity",
        },
        {
            "key": "dropped_objects",
            "title": "Dropped Objects",
            "starts_with": "CCV - Dropped Objects",
        },
        {
            "key": "entanglement_and_crushing",
            "title": "Entanglement & Crushing",
            "starts_with": "CCV - Entanglement and Crushing",
        },
        {
            "key": "fall_from_height",
            "title": "Fall from Height",
            "starts_with": "CCV - Fall From Height",
        },
        {
            "key": "hot_works",
            "title": "Hot Works",
            "starts_with": "CCV - Hot Works",
        },
        {
            "key": "lifting_operations",
            "title": "Lifting Operations",
            "starts_with": "CCV - Lifting Operations",
        },
        {
            "key": "uncontrolled_release_of_energy",
            "title": "Uncontrolled Release of Energy",
            "starts_with": "CCV - Uncontrolled Release of Energy",
        },
        {
            "key": "vehicles_and_mobile_equipment",
            "title": "Vehicles and Mobile Equipment",
            "starts_with": "CCV - Vehicles and Mobile Equipment",
        },
        {
            "key": "working_near_water",
            "title": "Working Near Water",
            "starts_with": "CCV - Working Near Water",
        },
    ]

    data = []

    for ccv in ccv_forms:
        row = get_average_compliance_for_ccv(
            title=ccv["title"],
            starts_with=ccv["starts_with"],
            project_scope_name=project_scope_name,
        )

        row["key"] = ccv["key"]
        data.append(row)

    return data


def get_average_compliance_for_ccv(title, starts_with, project_scope_name=None):
    where_clause, values = get_project_scope_condition(project_scope_name)

    values["starts_with"] = starts_with + "%"
    values["title"] = title
    values["starts_with_label"] = starts_with

    where_clause = append_condition(
        where_clause,
        """
        sm.form_submitted LIKE %(starts_with)s
        AND sm.compliance_percentage IS NOT NULL
        """,
    )

    sql = f"""
        SELECT
            %(title)s AS title,
            %(starts_with_label)s AS form_filter,
            ROUND(AVG(sm.compliance_percentage), 2) AS avg_compliance_percentage,
            COUNT(*) AS record_count
        FROM `tabSafety Metrics` sm
        LEFT JOIN `tabTask` t ON t.name = sm.parent
        {where_clause}
    """

    rows = run_sql(sql, values)

    if rows:
        return rows[0]

    return {
        "title": title,
        "form_filter": starts_with,
        "avg_compliance_percentage": None,
        "record_count": 0,
    }


def get_positive_and_at_risk_behaviours(project_scope_name=None):
    behaviour_sets = [
        {
            "behaviour_type": "Positive",
            "prefix": "pos",
        },
        {
            "behaviour_type": "At-Risk",
            "prefix": "neg",
        },
    ]

    categories = {
        "Positions of People": [
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
        ],
        "PPE": [
            "21",
            "22",
            "23",
            "24",
            "25",
            "26",
            "27",
        ],
        "Tools & Equipment": [
            "31",
            "32",
            "33",
        ],
        "Procedures": [
            "41",
            "42",
            "43",
            "44",
        ],
        "Work Area": [
            "51",
            "52",
            "53",
            "54",
        ],
    }

    data = []

    for behaviour_set in behaviour_sets:
        behaviour_type = behaviour_set["behaviour_type"]
        prefix = behaviour_set["prefix"]

        for category, suffixes in categories.items():
            fields = [f"{prefix}_{suffix}" for suffix in suffixes]

            field_expression = " + ".join([
                f"COALESCE(sm.`{fieldname}`, 0)"
                for fieldname in fields
            ])

            where_clause, values = get_project_scope_condition(project_scope_name)

            values["behaviour_type"] = behaviour_type
            values["category"] = category

            sql = f"""
                SELECT
                    %(behaviour_type)s AS behaviour_type,
                    %(category)s AS category,
                    SUM({field_expression}) AS value
                FROM `tabSafety Metrics` sm
                LEFT JOIN `tabTask` t ON t.name = sm.parent
                {where_clause}
            """

            rows = run_sql(sql, values)
            value = rows[0].get("value") if rows else 0
            value = int(value or 0)

            if value > 1:
                data.append({
                    "behaviour_type": behaviour_type,
                    "category": category,
                    "value": value,
                })

    data = sorted(
        data,
        key=lambda row: (row["behaviour_type"], -row["value"], row["category"]),
    )

    return data


def build_peri_dashboard_prompt(payload):
    compact_payload = json.dumps(payload, indent=2, default=str)

    return f"""
You are PERI, a Work Health and Safety AI assistant for Mine Site Support.

Analyse the following Shutdown Safety Metrics dashboard data.

The dashboard has been filtered by project scope where provided.

Your role:
- Identify the strongest positive trends.
- Identify the highest at-risk behaviour categories.
- Identify low compliance areas.
- Identify contractor, work area, form, and CCV focus areas.
- Provide practical supervisor-level actions.
- Avoid overstating certainty.
- Only use the data provided.
- Do not invent missing values.
- Use clear WHS language suitable for a shutdown/project team.

Dashboard data:
{compact_payload}

Return the response using this structure ONLY using Markdown formatting:
### Executive Summary
A short overview of what the dashboard is indicating using unordered list markdown.

### What Is Working Well
Summarise the strongest positive indicators using unordered list markdown. This could include high compliance areas, positive behaviour categories, or encouraging trends.

### Key At-Risk Trends
Highlight the most concerning behaviour categories, work areas, contractors, forms, or CCVs using unordered list markdown.

### Critical Control Focus
Call out any CCV areas that appear lower than expected or have limited data using unordered list markdown.

### Recommended Actions
Give practical actions for supervisors, HSE advisors, and project leads using unordered list markdown.

### Suggested Toolbox / Pre-Start Message
Provide a short message that could be used at the next pre-start using blockquote formatting.

### Data Confidence Notes
Mention any gaps, low record counts, or areas where more observations are needed using unordered list markdown.
"""