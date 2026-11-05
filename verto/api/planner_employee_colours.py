"""Employment Type colour configuration used by Planner employee accents."""

COLOUR_FIELD = "custom_planner_colour"


def ensure_employee_colour_field():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    create_custom_fields({
        "Employment Type": [{
            "fieldname": COLOUR_FIELD,
            "fieldtype": "Color",
            "label": "Planner Colour",
            "insert_after": "employee_type_name",
            "in_list_view": 1,
            "description": "Employee row and hover colour in the Planner. Leave blank to use blue.",
        }],
    }, update=False)
    return True
