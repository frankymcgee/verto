import frappe


# ---------------------------------------------------------------------
# Shared rule sets
# ---------------------------------------------------------------------

SHARED_RULE_SETS = {
    "task_work_order_rules": [
        {
            "name": "Set Work Order Number from Task",
            "trigger_fields": ["link_task", "scope_or_wo"],
            "required_fields": ["scope_or_wo", "link_task", "work_order_number"],
            "conditions": {
                "scope_or_wo": "Work Scope",
                "link_task": {"not_empty": True},
            },
            "lookup": {
                "doctype": "Task",
                "filters": {
                    "name": "{link_task}",
                },
                "fieldname": "work_order_number",
            },
            "set": {
                "work_order_number": "{lookup_value}",
            },
            "clear_if_empty": ["work_order_number"],
            "warning_if_empty": "No Work Order Number was found for the selected task.",
        },
        {
            "name": "Set Task from Work Order Number",
            "trigger_fields": ["work_order_number", "scope_or_wo"],
            "required_fields": ["scope_or_wo", "link_task", "work_order_number"],
            "conditions": {
                "scope_or_wo": "Work Order Number",
                "work_order_number": {"not_empty": True},
            },
            "lookup": {
                "doctype": "Task",
                "filters": {
                    "work_order_number": "{work_order_number}",
                },
                "fieldname": "name",
            },
            "set": {
                "link_task": "{lookup_value}",
            },
            "clear_if_empty": ["link_task"],
            "warning_if_empty": "No Task was found for the entered Work Order Number.",
        },
    ],
}


# ---------------------------------------------------------------------
# Compliance percentage setup
# ---------------------------------------------------------------------
# Add any DocType here that should calculate compliance_percentage from
# Select fields using:
# Yes = 1
# Yes (fixed on the spot) = 0.75
# No = 0
# N/A = 1
# ---------------------------------------------------------------------

COMPLIANCE_PERCENTAGE_DOCTYPES = {
    "Workplace Inspection",
    "Commitment Interaction",
    "Field Interaction",
    "Job Hazard Analysis Review",
    "Contractor Management Audit Checklist",
    "Prohibited and Restricted Tooling Checklist",
    "Safety Identification Rectification",
    "Supervisor BATB",
    "Weekly Summary",
}

COMPLIANCE_PERCENTAGE_FIELD = "compliance_percentage"

COMPLIANCE_RATING_MAP = {
    "Yes": 1,
    "Yes (fixed on the spot)": 0.75,
    "No": 0,
    "N/A": 1,
}

COMPLIANCE_SKIP_FIELDNAME_PARTS = [
    "safety_category",
    "improvement_required",
]


# ---------------------------------------------------------------------
# DocType rule assignment
# ---------------------------------------------------------------------

MOBILE_FIELD_RULES = {
    "Field Interaction": {
        "include": [
            "task_work_order_rules",
        ],
        "rules": [],
    },
    "Commitment Interaction": {
        "include": [
            "task_work_order_rules",
        ],
        "rules": [],
    },
    "Workplace Inspection": {
        "include": [
            "task_work_order_rules",
        ],
        "rules": [],
    },
    "Job Hazard Analysis Review": {
        "include": [
            "task_work_order_rules",
        ],
        "rules": [],
    },
    "Contractor Management Audit Checklist": {
        "include": [
            "task_work_order_rules",
        ],
        "rules": [],
    },
    "Prohibited and Restricted Tooling Checklist": {
        "include": [
            "task_work_order_rules",
        ],
        "rules": [],
    },
    "Safety Identification Rectification": {
        "include": [
            "task_work_order_rules",
        ],
        "rules": [],
    },
    "Supervisor BATB": {
        "include": [
            "task_work_order_rules",
        ],
        "rules": [],
    },
    "Weekly Summary": {
        "include": [
            "task_work_order_rules",
        ],
        "rules": [],
    },
}


# ---------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------

def render_template(value, values, context=None):
    context = context or {}

    if not isinstance(value, str):
        return value

    rendered = value

    for fieldname, field_value in values.items():
        rendered = rendered.replace("{" + fieldname + "}", str(field_value or ""))

    for key, context_value in context.items():
        rendered = rendered.replace("{" + key + "}", str(context_value or ""))

    return rendered


def condition_matches(expected, actual):
    if isinstance(expected, dict):
        if expected.get("not_empty"):
            return actual not in (None, "")

        if expected.get("empty"):
            return actual in (None, "")

        if "equals" in expected:
            return actual == expected.get("equals")

        if "not_equals" in expected:
            return actual != expected.get("not_equals")

        if "in" in expected:
            return actual in expected.get("in", [])

        if "not_in" in expected:
            return actual not in expected.get("not_in", [])

        if "contains" in expected:
            return str(expected.get("contains")) in str(actual or "")

        if "not_contains" in expected:
            return str(expected.get("not_contains")) not in str(actual or "")

        return False

    return actual == expected


def rule_conditions_match(rule, values):
    conditions = rule.get("conditions") or {}

    for fieldname, expected in conditions.items():
        actual = values.get(fieldname)

        if not condition_matches(expected, actual):
            return False

    return True


def get_allowed_fieldnames(doctype):
    meta = frappe.get_meta(doctype)
    return {df.fieldname for df in meta.fields if df.fieldname}


def get_rules_for_doctype(doctype):
    config = MOBILE_FIELD_RULES.get(doctype)

    if not config:
        return []

    # Backwards compatibility:
    # allow older style: "DocType": [rule, rule]
    if isinstance(config, list):
        return config

    rules = []

    for rule_set_name in config.get("include") or []:
        rules.extend(SHARED_RULE_SETS.get(rule_set_name, []))

    rules.extend(config.get("rules") or [])

    return rules


def get_rule_required_fields(rule):
    required_fields = set(rule.get("required_fields") or [])

    for fieldname in rule.get("trigger_fields") or []:
        required_fields.add(fieldname)

    for fieldname in (rule.get("conditions") or {}).keys():
        required_fields.add(fieldname)

    for fieldname in (rule.get("set") or {}).keys():
        required_fields.add(fieldname)

    for fieldname in rule.get("clear_if_empty") or []:
        required_fields.add(fieldname)

    return required_fields


def rule_can_run_on_doctype(parent_doctype, rule):
    parent_fields = get_allowed_fieldnames(parent_doctype)
    required_fields = get_rule_required_fields(rule)

    missing_fields = [
        fieldname
        for fieldname in required_fields
        if fieldname not in parent_fields
    ]

    if not missing_fields:
        return True

    # Shared rules skip safely when the DocType does not have all required fields.
    if rule.get("skip_if_missing_fields", True):
        return False

    frappe.throw(
        f"Mobile field rule '{rule.get('name')}' cannot run on {parent_doctype}. "
        f"Missing fields: {', '.join(missing_fields)}."
    )

    return False


def validate_rule_targets(parent_doctype, rule):
    parent_fields = get_allowed_fieldnames(parent_doctype)

    for target_fieldname in (rule.get("set") or {}).keys():
        if target_fieldname not in parent_fields:
            frappe.throw(
                f"Mobile field rule target field '{target_fieldname}' does not exist on {parent_doctype}."
            )

    for target_fieldname in rule.get("clear_if_empty") or []:
        if target_fieldname not in parent_fields:
            frappe.throw(
                f"Mobile field rule clear field '{target_fieldname}' does not exist on {parent_doctype}."
            )


def run_lookup(rule, values):
    lookup = rule.get("lookup")

    if not lookup:
        return None

    doctype = lookup.get("doctype")
    fieldname = lookup.get("fieldname")
    filters = lookup.get("filters") or {}

    if not doctype or not fieldname:
        return None

    if not frappe.has_permission(doctype, "read"):
        frappe.throw(f"You do not have permission to read {doctype}.", frappe.PermissionError)

    rendered_filters = {}

    for filter_fieldname, filter_value in filters.items():
        rendered_filters[filter_fieldname] = render_template(filter_value, values)

    # If any rendered filter is empty, do not run the lookup.
    for value in rendered_filters.values():
        if value in (None, ""):
            return None

    return frappe.db.get_value(
        doctype,
        rendered_filters,
        fieldname,
    )


def apply_set_values(rule, values, context):
    updates = {}

    for target_fieldname, template_value in (rule.get("set") or {}).items():
        updates[target_fieldname] = render_template(template_value, values, context)

    return updates


# ---------------------------------------------------------------------
# Compliance calculation helpers
# ---------------------------------------------------------------------

def doctype_has_field(doctype, fieldname):
    try:
        return frappe.get_meta(doctype).has_field(fieldname)
    except Exception:
        return False


def is_compliance_select_field(df):
    if df.fieldtype != "Select":
        return False

    fieldname = df.fieldname or ""

    for skip_part in COMPLIANCE_SKIP_FIELDNAME_PARTS:
        if skip_part in fieldname:
            return False

    return True


def should_run_compliance_calculation(doctype, changed_fieldname=None):
    if doctype not in COMPLIANCE_PERCENTAGE_DOCTYPES:
        return False

    if not doctype_has_field(doctype, COMPLIANCE_PERCENTAGE_FIELD):
        return False

    if not changed_fieldname:
        return True

    meta = frappe.get_meta(doctype)
    df = meta.get_field(changed_fieldname)

    if not df:
        return False

    return is_compliance_select_field(df)


def calculate_compliance_percentage(doctype, values):
    meta = frappe.get_meta(doctype)

    total_rating = 0
    count = 0

    for df in meta.fields:
        fieldname = df.fieldname

        if not fieldname:
            continue

        if not is_compliance_select_field(df):
            continue

        field_value = values.get(fieldname)

        if field_value in (None, ""):
            continue

        if field_value in COMPLIANCE_RATING_MAP:
            total_rating += COMPLIANCE_RATING_MAP[field_value]
            count += 1

    if not count:
        return 0

    return round((total_rating / count) * 100, 2)


def run_compliance_calculation(doctype, changed_fieldname, values):
    if not should_run_compliance_calculation(doctype, changed_fieldname):
        return {}

    return {
        COMPLIANCE_PERCENTAGE_FIELD: calculate_compliance_percentage(
            doctype=doctype,
            values=values,
        )
    }


# ---------------------------------------------------------------------
# Main rule runner
# ---------------------------------------------------------------------

def run_mobile_field_rules(doctype, changed_fieldname, values):
    updates = {}
    messages = []
    warnings = []

    rules = get_rules_for_doctype(doctype)

    for rule in rules:
        trigger_fields = rule.get("trigger_fields") or []

        if trigger_fields and changed_fieldname not in trigger_fields:
            continue

        if not rule_can_run_on_doctype(doctype, rule):
            continue

        validate_rule_targets(doctype, rule)

        if not rule_conditions_match(rule, values):
            continue

        lookup_value = run_lookup(rule, values)

        context = {
            "lookup_value": lookup_value,
        }

        if rule.get("lookup") and lookup_value in (None, ""):
            for fieldname in rule.get("clear_if_empty") or []:
                updates[fieldname] = ""

            if rule.get("warning_if_empty"):
                warnings.append(rule.get("warning_if_empty"))

            continue

        updates.update(apply_set_values(rule, values, context))

        if rule.get("message"):
            messages.append(render_template(rule.get("message"), values, context))

    compliance_updates = run_compliance_calculation(
        doctype=doctype,
        changed_fieldname=changed_fieldname,
        values={**values, **updates},
    )

    updates.update(compliance_updates)

    return {
        "values": updates,
        "messages": messages,
        "warnings": warnings,
    }


def handle_mobile_field_change(
    doctype,
    mobile_doctype,
    changed_fieldname,
    values,
    user,
):
    return run_mobile_field_rules(
        doctype=doctype,
        changed_fieldname=changed_fieldname,
        values=values,
    )


def apply_mobile_before_save_calculations(doctype, values):
    values = values or {}

    if doctype in COMPLIANCE_PERCENTAGE_DOCTYPES and doctype_has_field(
        doctype,
        COMPLIANCE_PERCENTAGE_FIELD,
    ):
        values[COMPLIANCE_PERCENTAGE_FIELD] = calculate_compliance_percentage(
            doctype=doctype,
            values=values,
        )

    return values