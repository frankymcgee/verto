from __future__ import annotations

import frappe


_TRUTHY_PROPERTY_VALUES = {"1", "true", "yes"}


def before_tests() -> None:
    """Relax only Verto-managed Project requirements while tests are running.

    ERPNext's upstream test bootstrap creates intentionally minimal Project
    records. Verto makes additional Project fields mandatory through Custom
    Fields and Property Setters, which is correct for production but prevents
    those upstream fixtures from being created. The Frappe ``before_tests``
    hook runs immediately before dependency records are generated, so changing
    the cached DocType metadata here keeps production schema and stored
    customization records untouched.
    """
    project_meta = frappe.get_meta("Project")

    for fieldname in _get_project_fields_made_mandatory_by_customization():
        field = project_meta.get_field(fieldname)
        if field:
            field.reqd = 0


def _get_project_fields_made_mandatory_by_customization() -> set[str]:
    """Return Project fields made mandatory outside ERPNext's base schema."""
    fieldnames = set(
        frappe.get_all(
            "Custom Field",
            filters={"dt": "Project", "reqd": 1},
            pluck="fieldname",
        )
    )

    property_setters = frappe.get_all(
        "Property Setter",
        filters={
            "doc_type": "Project",
            "doctype_or_field": "DocField",
            "property": "reqd",
        },
        fields=["field_name", "value"],
    )
    fieldnames.update(
        row.field_name
        for row in property_setters
        if row.field_name
        and str(row.value).strip().lower() in _TRUTHY_PROPERTY_VALUES
    )

    return fieldnames
