import frappe


MOBILE_FIELD_RULES = {
    # Add DocType-specific rules here.
    # Example below assumes the fields exist on this DocType.
    "Field Interaction": [
        {
            "name": "Set Work Order Number from Task",
            "trigger_fields": ["link_task", "scope_or_wo"],
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

    # Example:
    # "Pre Commencement Audit": [
    #     {
    #         "name": "Set Work Order Number from Task",
    #         "trigger_fields": ["link_task", "scope_or_wo"],
    #         "conditions": {
    #             "scope_or_wo": "Work Scope",
    #             "link_task": {"not_empty": True},
    #         },
    #         "lookup": {
    #             "doctype": "Task",
    #             "filters": {
    #                 "name": "{link_task}",
    #             },
    #             "fieldname": "work_order_number",
    #         },
    #         "set": {
    #             "work_order_number": "{lookup_value}",
    #         },
    #         "clear_if_empty": ["work_order_number"],
    #         "warning_if_empty": "No Work Order Number was found for the selected task.",
    #     },
    # ],
}


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


def run_mobile_field_rules(doctype, changed_fieldname, values):
    updates = {}
    messages = []
    warnings = []

    rules = MOBILE_FIELD_RULES.get(doctype, [])

    for rule in rules:
        trigger_fields = rule.get("trigger_fields") or []

        if trigger_fields and changed_fieldname not in trigger_fields:
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