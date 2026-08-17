import json
import frappe


@frappe.whitelist()
def get_shutdown_safety_dashboard_context(project_scope_name=None, project_name=None):
    """
    Returns structured Shutdown Safety Metrics and Shutdown Incident Tracker
    dashboard data for PERI/Raven AI.

    Filters:
    - project_scope_name: used for the existing Safety Metrics charts through
      Task.project_scope_name.
    - project_name: used for Shutdown Incident Tracker charts through the
      actual incident table column `tabShutdown Incident Tracker`.project_name.

    The incident tracker filter is deliberately strict. Incident SQL always
    filters against `tabShutdown Incident Tracker`.project_name. If project_name
    is not supplied by Raven/PERI, project_scope_name is used as the incident
    project-name value. If neither value is supplied, the incident section
    returns no incident rows instead of returning every project's incidents.
    """

    project_scope_name = clean_optional_value(project_scope_name)
    project_name = clean_optional_value(project_name)

    # Raven/PERI often supplies only project_scope_name from the dashboard
    # function call. For incident data, the actual SQL column to filter is
    # `tabShutdown Incident Tracker`.project_name, so we use project_name when
    # it is explicitly supplied and otherwise fall back to project_scope_name.
    #
    # This keeps the external filter name compatible with the existing Safety
    # Metrics flow while still applying the incident SQL filter to the real
    # incident table column.
    incident_project_name = project_name or project_scope_name
    incident_filter_context = get_incident_filter_context(incident_project_name)

    payload = {
        "dashboard": "Shutdown Safety Metrics",
        "workbook": "HL Safety Metrics",
        "filters": {
            "project_scope_name": project_scope_name,
            "project_name": project_name,
            "incident_project_name_applied": incident_project_name,
            "incident_filter": incident_filter_context,
        },
        "charts": {
            "compliance_trend": get_compliance_trend(project_scope_name),
            "work_area_compliance": get_work_area_compliance(project_scope_name),
            "contractor_compliance": get_contractor_compliance(project_scope_name),
            "areas_for_improvement": get_areas_for_improvement(project_scope_name),
            "form_compliance": get_form_compliance_cards(project_scope_name),
            "critical_control_verification": get_ccv_compliance_cards(project_scope_name),
            "positive_and_at_risk_behaviours": get_positive_and_at_risk_behaviours(project_scope_name),
            "shutdown_incident_tracker": {
                "filter_validation": get_incident_filter_validation(incident_project_name),
                "summary": get_incident_summary(incident_project_name),
                "incident_trend": get_incident_trend(incident_project_name),
                "incident_times": get_incident_times(incident_project_name),
                "incidents_by_shift": get_incidents_by_shift(incident_project_name),
                "incidents_by_day_of_week": get_incidents_by_day_of_week(incident_project_name),
                "incidents_by_classification": get_incidents_by_classification(incident_project_name),
                "incidents_by_rating": get_incidents_by_rating(incident_project_name),
                "incidents_by_status": get_incidents_by_status(incident_project_name),
                "incidents_by_contractor": get_incidents_by_contractor(incident_project_name),
                "incidents_by_work_area": get_incidents_by_work_area(incident_project_name),
                "incidents_by_consequence": get_incidents_by_consequence(incident_project_name),
                "incidents_by_likelihood": get_incidents_by_likelihood(incident_project_name),
                "risk_matrix": get_incident_risk_matrix(incident_project_name),
                "shift_classification_breakdown": get_shift_classification_breakdown(incident_project_name),
                "pending_assessment_incidents": get_pending_assessment_incidents(incident_project_name),
                "high_priority_incidents": get_high_priority_incidents(incident_project_name),
            },
        },
    }

    payload["peri_prompt"] = build_peri_dashboard_prompt(payload)

    return payload

def clean_optional_value(value):
    if value in [None, "", "null", "undefined", "None"]:
        return None

    return value


def append_condition(where_clause, condition):
    """
    Safely append an SQL condition to an existing WHERE clause.

    The appended condition is always wrapped in parentheses. This is important
    when a condition contains OR clauses. Without parentheses, SQL operator
    precedence can allow records outside the project filter to be returned, for
    example:

        WHERE sit.project_name = %(project_name)s
        AND high_condition
        OR open_condition

    In that example, open_condition can bypass the project filter. Wrapping the
    appended condition prevents cross-project incident leakage.
    """

    condition = (condition or "").strip()

    if not condition:
        return where_clause

    if where_clause:
        return f"{where_clause} AND ({condition})"

    return f"WHERE ({condition})"


def run_sql(sql, values=None):
    return frappe.db.sql(sql, values or {}, as_dict=True)


# -----------------------------------------------------------------------------
# Safety Metrics helpers
# -----------------------------------------------------------------------------

def get_project_scope_condition(project_scope_name=None):
    if not project_scope_name:
        return "", {}

    return "WHERE t.project_scope_name = %(project_scope_name)s", {
        "project_scope_name": project_scope_name,
    }


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


# -----------------------------------------------------------------------------
# Shutdown Incident Tracker helpers
# -----------------------------------------------------------------------------

def get_incident_filter_context(project_name=None):
    """
    Return filter metadata for the Shutdown Incident Tracker section.

    This uses the actual database field on the Shutdown Incident Tracker table:
    `tabShutdown Incident Tracker`.project_name.
    """

    project_name = clean_optional_value(project_name)

    return {
        "input": project_name,
        "table": "tabShutdown Incident Tracker",
        "field": "project_name",
        "sql_filter": "sit.project_name = %(project_name)s",
        "filter_applied": bool(project_name),
        "filter_mode": "project_name" if project_name else "no_project_name_filter_supplied",
        "warning": None if project_name else "No project_name was supplied. Incident rows have been deliberately suppressed to prevent cross-project analysis.",
    }


def get_incident_project_condition(project_name=None):
    project_name = clean_optional_value(project_name)

    # Important: no project_name must not mean all incidents. Returning every
    # incident can contaminate PERI analysis with records from other projects.
    # Every Shutdown Incident Tracker chart must use this condition.
    if not project_name:
        return "WHERE 1 = 0", {}

    return "WHERE TRIM(IFNULL(sit.project_name, '')) = TRIM(%(project_name)s)", {
        "project_name": project_name,
    }


def get_incident_filter_validation(project_name=None):
    """
    Returns a small validation block showing exactly which incident project_name
    values are being included after the project filter is applied.

    In a correctly filtered result this should contain either no rows or a
    single project_name matching the supplied project_name.
    """

    where_clause, values = get_incident_project_condition(project_name)

    sql = f"""
        SELECT
            COALESCE(NULLIF(sit.project_name, ''), 'Not specified') AS project_name,
            COUNT(*) AS count
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY COALESCE(NULLIF(sit.project_name, ''), 'Not specified')
        ORDER BY count DESC, project_name ASC
        LIMIT 20
    """

    return run_sql(sql, values)


def get_incident_field_label(field_expression, fallback="Not specified"):
    return f"COALESCE(NULLIF({field_expression}, ''), '{fallback}')"


def get_incident_shift_case():
    return """
        CASE
            WHEN sit.time_range IN (
                '06:00 - 09:00',
                '09:00 - 12:00',
                '12:00 - 15:00',
                '15:00 - 18:00'
            ) THEN 'Day Shift'
            WHEN sit.time_range IN (
                '18:00 - 21:00',
                '21:00 - 00:00',
                '00:00 - 03:00',
                '03:00 - 06:00'
            ) THEN 'Night Shift'
            ELSE 'Not specified'
        END
    """


def get_incident_time_order_expression(field_expression="sit.time_range"):
    return f"""
        CASE {field_expression}
            WHEN '00:00 - 03:00' THEN 1
            WHEN '03:00 - 06:00' THEN 2
            WHEN '06:00 - 09:00' THEN 3
            WHEN '09:00 - 12:00' THEN 4
            WHEN '12:00 - 15:00' THEN 5
            WHEN '15:00 - 18:00' THEN 6
            WHEN '18:00 - 21:00' THEN 7
            WHEN '21:00 - 00:00' THEN 8
            ELSE 99
        END
    """


def get_day_of_week_order_expression():
    return """
        CASE DAYOFWEEK(sit.date_occured)
            WHEN 2 THEN 1
            WHEN 3 THEN 2
            WHEN 4 THEN 3
            WHEN 5 THEN 4
            WHEN 6 THEN 5
            WHEN 7 THEN 6
            WHEN 1 THEN 7
            ELSE 99
        END
    """


def get_risk_rating_order_expression(field_expression="sit.risk_rating"):
    return f"""
        CASE
            WHEN IFNULL({field_expression}, '') = '' THEN 999
            WHEN UPPER({field_expression}) = 'PENDING' THEN 998
            WHEN UPPER({field_expression}) LIKE 'LOW%%' THEN 100
            WHEN UPPER({field_expression}) LIKE 'MEDIUM%%' THEN 200
            WHEN UPPER({field_expression}) LIKE 'MED%%' THEN 200
            WHEN UPPER({field_expression}) LIKE 'HIGH%%' THEN 300
            WHEN UPPER({field_expression}) LIKE 'EXTREME%%' THEN 400
            ELSE 500
        END
    """


def add_percentages(rows, count_key="count", percentage_key="percentage"):
    total = sum(int(row.get(count_key) or 0) for row in rows)

    for row in rows:
        count = int(row.get(count_key) or 0)
        row[percentage_key] = round((count / total) * 100, 2) if total else 0

    return rows


def get_incident_summary(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)

    sql = f"""
        SELECT
            COUNT(*) AS total_incidents,
            SUM(CASE WHEN IFNULL(sit.work_related, 0) = 1 THEN 1 ELSE 0 END) AS work_related_incidents,
            SUM(CASE WHEN IFNULL(sit.work_related, 0) = 0 THEN 1 ELSE 0 END) AS non_work_related_incidents,
            SUM(CASE WHEN sit.current_status = 'Closed' THEN 1 ELSE 0 END) AS closed_incidents,
            SUM(CASE WHEN IFNULL(sit.current_status, '') != 'Closed' THEN 1 ELSE 0 END) AS open_incidents,
            SUM(CASE WHEN IFNULL(sit.current_status, '') = 'Evidence Gathering' THEN 1 ELSE 0 END) AS evidence_gathering_incidents,
            SUM(CASE WHEN IFNULL(sit.current_status, '') = 'Investigation' THEN 1 ELSE 0 END) AS investigation_incidents,
            SUM(CASE WHEN IFNULL(sit.current_status, '') = 'Finalising' THEN 1 ELSE 0 END) AS finalising_incidents,
            SUM(CASE
                WHEN IFNULL(sit.risk_rating, '') = ''
                    OR UPPER(sit.risk_rating) = 'PENDING'
                    OR UPPER(sit.consequence) = 'PENDING'
                    OR UPPER(sit.likelihood) = 'PENDING'
                THEN 1 ELSE 0
            END) AS pending_risk_assessment_incidents,
            SUM(CASE
                WHEN UPPER(IFNULL(sit.risk_rating, '')) LIKE 'HIGH%%'
                    OR UPPER(IFNULL(sit.risk_rating, '')) LIKE 'EXTREME%%'
                    OR UPPER(IFNULL(sit.consequence, '')) IN ('MAJOR', 'SEVERE', 'CATASTROPHIC')
                THEN 1 ELSE 0
            END) AS high_priority_incidents,
            MIN(sit.date_occured) AS first_incident_date,
            MAX(sit.date_occured) AS latest_incident_date
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
    """

    rows = run_sql(sql, values)

    if not rows:
        return {}

    return rows[0]


def get_incident_trend(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)

    where_clause = append_condition(
        where_clause,
        "sit.date_occured IS NOT NULL",
    )

    sql = f"""
        SELECT
            DATE(sit.date_occured) AS date_occured,
            COUNT(*) AS count,
            SUM(CASE WHEN IFNULL(sit.work_related, 0) = 1 THEN 1 ELSE 0 END) AS work_related_count,
            SUM(CASE WHEN IFNULL(sit.current_status, '') != 'Closed' THEN 1 ELSE 0 END) AS open_count,
            SUM(CASE
                WHEN UPPER(IFNULL(sit.risk_rating, '')) LIKE 'HIGH%%'
                    OR UPPER(IFNULL(sit.risk_rating, '')) LIKE 'EXTREME%%'
                    OR UPPER(IFNULL(sit.consequence, '')) IN ('MAJOR', 'SEVERE', 'CATASTROPHIC')
                THEN 1 ELSE 0
            END) AS high_priority_count
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY DATE(sit.date_occured)
        ORDER BY DATE(sit.date_occured) ASC
        LIMIT 100
    """

    return run_sql(sql, values)


def get_incident_times(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    time_label = get_incident_field_label("sit.time_range")
    time_order = get_incident_time_order_expression("sit.time_range")

    sql = f"""
        SELECT
            {time_label} AS time_range,
            COUNT(*) AS count
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY {time_label}, {time_order}
        ORDER BY {time_order} ASC, count DESC
        LIMIT 100
    """

    rows = run_sql(sql, values)
    return add_percentages(rows)


def get_incidents_by_shift(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    shift_case = get_incident_shift_case()

    sql = f"""
        SELECT
            {shift_case} AS shift,
            COUNT(*) AS count,
            SUM(CASE WHEN IFNULL(sit.work_related, 0) = 1 THEN 1 ELSE 0 END) AS work_related_count,
            SUM(CASE WHEN IFNULL(sit.current_status, '') != 'Closed' THEN 1 ELSE 0 END) AS open_count,
            SUM(CASE
                WHEN UPPER(IFNULL(sit.risk_rating, '')) LIKE 'HIGH%%'
                    OR UPPER(IFNULL(sit.risk_rating, '')) LIKE 'EXTREME%%'
                    OR UPPER(IFNULL(sit.consequence, '')) IN ('MAJOR', 'SEVERE', 'CATASTROPHIC')
                THEN 1 ELSE 0
            END) AS high_priority_count
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY {shift_case}
        ORDER BY
            CASE {shift_case}
                WHEN 'Day Shift' THEN 1
                WHEN 'Night Shift' THEN 2
                ELSE 3
            END
    """

    rows = run_sql(sql, values)
    return add_percentages(rows)


def get_incidents_by_day_of_week(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    day_order = get_day_of_week_order_expression()

    where_clause = append_condition(
        where_clause,
        "sit.date_occured IS NOT NULL",
    )

    sql = f"""
        SELECT
            DAYNAME(sit.date_occured) AS day_of_week,
            COUNT(*) AS count
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY DAYNAME(sit.date_occured), {day_order}
        ORDER BY {day_order} ASC
        LIMIT 100
    """

    rows = run_sql(sql, values)
    return add_percentages(rows)


def get_incidents_by_classification(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    classification_label = get_incident_field_label("sit.classification")

    sql = f"""
        SELECT
            {classification_label} AS classification,
            COUNT(*) AS count,
            SUM(CASE WHEN IFNULL(sit.work_related, 0) = 1 THEN 1 ELSE 0 END) AS work_related_count,
            SUM(CASE WHEN IFNULL(sit.current_status, '') != 'Closed' THEN 1 ELSE 0 END) AS open_count
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY {classification_label}
        ORDER BY count DESC, classification ASC
        LIMIT 100
    """

    rows = run_sql(sql, values)
    return add_percentages(rows)


def get_incidents_by_rating(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    rating_label = get_incident_field_label("sit.risk_rating", "Pending")
    risk_order = get_risk_rating_order_expression("sit.risk_rating")

    sql = f"""
        SELECT
            {rating_label} AS risk_rating,
            COUNT(*) AS count,
            SUM(CASE WHEN IFNULL(sit.current_status, '') != 'Closed' THEN 1 ELSE 0 END) AS open_count,
            MIN({risk_order}) AS risk_order
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY {rating_label}
        ORDER BY risk_order DESC, count DESC, risk_rating ASC
        LIMIT 100
    """

    rows = run_sql(sql, values)

    for row in rows:
        row.pop("risk_order", None)

    return add_percentages(rows)


def get_incidents_by_status(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    status_label = get_incident_field_label("sit.current_status")

    sql = f"""
        SELECT
            {status_label} AS current_status,
            COUNT(*) AS count,
            SUM(CASE WHEN IFNULL(sit.work_related, 0) = 1 THEN 1 ELSE 0 END) AS work_related_count
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY {status_label}
        ORDER BY
            CASE {status_label}
                WHEN 'Evidence Gathering' THEN 1
                WHEN 'Investigation' THEN 2
                WHEN 'Finalising' THEN 3
                WHEN 'Closed' THEN 4
                ELSE 5
            END,
            count DESC
        LIMIT 100
    """

    rows = run_sql(sql, values)
    return add_percentages(rows)


def get_incidents_by_contractor(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    contractor_label = get_incident_field_label("sit.contractor")

    sql = f"""
        SELECT
            {contractor_label} AS contractor,
            COUNT(*) AS count,
            SUM(CASE WHEN IFNULL(sit.work_related, 0) = 1 THEN 1 ELSE 0 END) AS work_related_count,
            SUM(CASE WHEN IFNULL(sit.current_status, '') != 'Closed' THEN 1 ELSE 0 END) AS open_count,
            SUM(CASE
                WHEN UPPER(IFNULL(sit.risk_rating, '')) LIKE 'HIGH%%'
                    OR UPPER(IFNULL(sit.risk_rating, '')) LIKE 'EXTREME%%'
                    OR UPPER(IFNULL(sit.consequence, '')) IN ('MAJOR', 'SEVERE', 'CATASTROPHIC')
                THEN 1 ELSE 0
            END) AS high_priority_count
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY {contractor_label}
        ORDER BY count DESC, high_priority_count DESC, contractor ASC
        LIMIT 100
    """

    rows = run_sql(sql, values)
    return add_percentages(rows)


def get_incidents_by_work_area(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    work_area_label = get_incident_field_label("sit.work_area")

    sql = f"""
        SELECT
            {work_area_label} AS work_area,
            COUNT(*) AS count,
            SUM(CASE WHEN IFNULL(sit.work_related, 0) = 1 THEN 1 ELSE 0 END) AS work_related_count,
            SUM(CASE WHEN IFNULL(sit.current_status, '') != 'Closed' THEN 1 ELSE 0 END) AS open_count,
            SUM(CASE
                WHEN UPPER(IFNULL(sit.risk_rating, '')) LIKE 'HIGH%%'
                    OR UPPER(IFNULL(sit.risk_rating, '')) LIKE 'EXTREME%%'
                    OR UPPER(IFNULL(sit.consequence, '')) IN ('MAJOR', 'SEVERE', 'CATASTROPHIC')
                THEN 1 ELSE 0
            END) AS high_priority_count
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY {work_area_label}
        ORDER BY count DESC, high_priority_count DESC, work_area ASC
        LIMIT 100
    """

    rows = run_sql(sql, values)
    return add_percentages(rows)


def get_incidents_by_consequence(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    consequence_label = get_incident_field_label("sit.consequence", "Pending")

    sql = f"""
        SELECT
            {consequence_label} AS consequence,
            COUNT(*) AS count
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY {consequence_label}
        ORDER BY
            CASE {consequence_label}
                WHEN 'Catastrophic' THEN 7
                WHEN 'Severe' THEN 6
                WHEN 'Major' THEN 5
                WHEN 'Serious' THEN 4
                WHEN 'Moderate' THEN 3
                WHEN 'Minor' THEN 2
                WHEN 'PENDING' THEN 1
                WHEN 'Pending' THEN 1
                ELSE 0
            END DESC,
            count DESC
        LIMIT 100
    """

    rows = run_sql(sql, values)
    return add_percentages(rows)


def get_incidents_by_likelihood(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    likelihood_label = get_incident_field_label("sit.likelihood", "Pending")

    sql = f"""
        SELECT
            {likelihood_label} AS likelihood,
            COUNT(*) AS count
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY {likelihood_label}
        ORDER BY
            CASE {likelihood_label}
                WHEN 'Almost Certain' THEN 6
                WHEN 'Highly Likely' THEN 5
                WHEN 'Likely' THEN 4
                WHEN 'Possible' THEN 3
                WHEN 'Unlikely' THEN 2
                WHEN 'Highly Unlikely' THEN 1
                WHEN 'PENDING' THEN 0
                WHEN 'Pending' THEN 0
                ELSE 0
            END DESC,
            count DESC
        LIMIT 100
    """

    rows = run_sql(sql, values)
    return add_percentages(rows)


def get_incident_risk_matrix(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    consequence_label = get_incident_field_label("sit.consequence", "Pending")
    likelihood_label = get_incident_field_label("sit.likelihood", "Pending")
    rating_label = get_incident_field_label("sit.risk_rating", "Pending")
    risk_order = get_risk_rating_order_expression("sit.risk_rating")

    sql = f"""
        SELECT
            {consequence_label} AS consequence,
            {likelihood_label} AS likelihood,
            {rating_label} AS risk_rating,
            COUNT(*) AS count,
            MIN({risk_order}) AS risk_order
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY {consequence_label}, {likelihood_label}, {rating_label}
        ORDER BY risk_order DESC, count DESC, consequence ASC, likelihood ASC
        LIMIT 100
    """

    rows = run_sql(sql, values)

    for row in rows:
        row.pop("risk_order", None)

    return rows


def get_shift_classification_breakdown(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    shift_case = get_incident_shift_case()
    classification_label = get_incident_field_label("sit.classification")

    sql = f"""
        SELECT
            {shift_case} AS shift,
            {classification_label} AS classification,
            COUNT(*) AS count,
            SUM(CASE WHEN IFNULL(sit.work_related, 0) = 1 THEN 1 ELSE 0 END) AS work_related_count
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        GROUP BY {shift_case}, {classification_label}
        ORDER BY
            CASE {shift_case}
                WHEN 'Day Shift' THEN 1
                WHEN 'Night Shift' THEN 2
                ELSE 3
            END,
            count DESC,
            classification ASC
        LIMIT 100
    """

    return run_sql(sql, values)


def get_pending_assessment_incidents(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)

    where_clause = append_condition(
        where_clause,
        """
        IFNULL(sit.risk_rating, '') = ''
        OR UPPER(IFNULL(sit.risk_rating, '')) = 'PENDING'
        OR UPPER(IFNULL(sit.consequence, '')) = 'PENDING'
        OR UPPER(IFNULL(sit.likelihood, '')) = 'PENDING'
        """,
    )

    sql = f"""
        SELECT
            sit.name,
            sit.date_occured,
            sit.time_range,
            {get_incident_shift_case()} AS shift,
            sit.contractor,
            sit.work_area,
            sit.classification,
            sit.consequence,
            sit.likelihood,
            sit.risk_rating,
            sit.current_status,
            sit.work_related,
            sit.description
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        ORDER BY sit.date_occured DESC, sit.modified DESC
        LIMIT 25
    """

    return run_sql(sql, values)


def get_high_priority_incidents(project_name=None):
    where_clause, values = get_incident_project_condition(project_name)
    risk_order = get_risk_rating_order_expression("sit.risk_rating")

    where_clause = append_condition(
        where_clause,
        """
        UPPER(IFNULL(sit.risk_rating, '')) LIKE 'HIGH%%'
        OR UPPER(IFNULL(sit.risk_rating, '')) LIKE 'EXTREME%%'
        OR UPPER(IFNULL(sit.consequence, '')) IN ('MAJOR', 'SEVERE', 'CATASTROPHIC')
        OR IFNULL(sit.current_status, '') != 'Closed'
        """,
    )

    sql = f"""
        SELECT
            sit.name,
            sit.date_occured,
            sit.time_range,
            {get_incident_shift_case()} AS shift,
            sit.contractor,
            sit.work_area,
            sit.classification,
            sit.consequence,
            sit.likelihood,
            sit.risk_rating,
            sit.current_status,
            sit.work_related,
            sit.description,
            sit.notes,
            {risk_order} AS risk_order
        FROM `tabShutdown Incident Tracker` sit
        {where_clause}
        ORDER BY risk_order DESC, sit.date_occured DESC, sit.modified DESC
        LIMIT 25
    """

    rows = run_sql(sql, values)

    for row in rows:
        row.pop("risk_order", None)

    return rows


# -----------------------------------------------------------------------------
# PERI prompt
# -----------------------------------------------------------------------------

def build_peri_dashboard_prompt(payload):
    compact_payload = json.dumps(payload, indent=2, default=str)

    return f"""
You are PERI, a Work Health and Safety AI assistant for Mine Site Support.

Analyse the following Shutdown Safety Metrics and Shutdown Incident Tracker dashboard data.

The Safety Metrics data is filtered by project scope where provided.
The Shutdown Incident Tracker data is filtered against `tabShutdown Incident Tracker`.project_name using the supplied project_name, or project_scope_name as a fallback when project_name is not supplied.

Your role:
- Identify the strongest positive trends.
- Identify the highest at-risk behaviour categories.
- Identify low compliance areas.
- Identify contractor, work area, form, and CCV focus areas.
- Analyse incident frequency by time range, day shift, night shift, day of week, classification, risk rating, status, contractor, work area, consequence, and likelihood.
- Identify whether incidents appear concentrated by shift, time of day, contractor, classification, risk rating, or work area.
- Identify open investigation or evidence-gathering bottlenecks.
- Identify pending risk assessments and explain why they should be closed out promptly.
- Provide practical supervisor-level actions to minimise repeat incidents.
- Avoid overstating certainty or claiming root causes that are not in the data.
- Only use the data provided.
- Do not invent missing values.
- Use clear WHS language suitable for a shutdown/project team.

When analysing incidents:
- Treat higher counts as areas for review, not proof of poor performance by themselves.
- If night shift has more incidents, discuss fatigue, lighting, supervision visibility, handover quality, permit controls, and work-front congestion as possible review areas only where relevant.
- If day shift has more incidents, discuss work volume, simultaneous operations, interface management, congestion, and task-risk alignment as possible review areas only where relevant.
- If risk ratings are mostly Low, still call out repeat low-level events as potential weak signals.
- If risk ratings, consequence, or likelihood are Pending, call this out as a data quality and risk-review issue.
- Prioritise recommendations that supervisors and HSE advisors can act on immediately.

Dashboard data:
{compact_payload}

Return the response using this structure ONLY using Markdown formatting:
### Executive Summary
A short overview of what the dashboard is indicating using unordered list markdown.

### What Is Working Well
Summarise the strongest positive indicators using unordered list markdown. This could include high compliance areas, positive behaviour categories, closed incident status, low-risk incident ratings, or encouraging trends.

### Key At-Risk Trends
Highlight the most concerning behaviour categories, work areas, contractors, incident classifications, shifts, time ranges, risk ratings, statuses, forms, or CCVs using unordered list markdown.

### Incident Tracker Focus
Summarise the main incident patterns by rating, classification, shift, time range, contractor, work area, consequence, and likelihood using unordered list markdown.

### Critical Control Focus
Call out any CCV areas that appear lower than expected or have limited data using unordered list markdown.

### Recommended Actions
Give practical actions for supervisors, HSE advisors, and project leads to reduce repeat incidents and strengthen controls using unordered list markdown.

### Suggested Toolbox / Pre-Start Message
Provide a short message that could be used at the next pre-start using blockquote formatting.

### Data Confidence Notes
Mention any gaps, pending risk assessments, low record counts, missing fields, or areas where more observations are needed using unordered list markdown.
"""
