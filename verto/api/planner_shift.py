"""Permission-checked edits to allocated shifts from the Planner."""

import frappe
from frappe import _
from frappe.utils import getdate


EDITABLE_FIELDS = frozenset({
	"employee", "shift_type", "start_date", "end_date", "shift_location",
	"custom_project", "custom_project_designation", "status", "note",
})


def _refresh_link_details(doc, changed_links):
	# Fetch-if-empty fields otherwise retain the previous employee/project's
	# details. Submitted documents also skip fetching fields without allow_on_submit.
	for link_field in changed_links:
		fields = doc.meta.get_fields_to_fetch(link_field)
		if not fields:
			continue
		sources = list(dict.fromkeys(df.fetch_from.split(".")[-1] for df in fields))
		link = doc.get(link_field)
		values = {}
		if link:
			doctype = doc.meta.get_field(link_field).options
			values = frappe.db.get_value(doctype, link, sources, as_dict=True)
			if not values:
				frappe.throw(_("Could not find {0}: {1}").format(doctype, link), frappe.LinkValidationError)
		for df in fields:
			doc.set(df.fieldname, values.get(df.fetch_from.split(".")[-1]))


@frappe.whitelist(methods=["POST"])
def update(name: str, expected_modified: str | None = None, values=None):
	# Lock the allocation so two planners cannot overwrite the same revision.
	doc = frappe.get_doc("Shift Assignment", name, for_update=True)
	doc.check_permission("read")
	doc.check_permission("write")
	if doc.docstatus == 2:
		frappe.throw(_("Cancelled Shift Assignments cannot be edited."))
	if doc.docstatus == 1:
		doc.check_permission("submit")
	if not expected_modified or str(doc.modified) != str(expected_modified):
		frappe.throw(_("This Shift Assignment changed elsewhere. Close and reopen it before saving."), frappe.TimestampMismatchError)

	values = frappe.parse_json(values) if isinstance(values, str) else values
	if not isinstance(values, dict):
		frappe.throw(_("Invalid Shift Assignment values."))
	write_levels = set(doc.get_permlevel_access("write"))
	for fieldname, value in values.items():
		df = doc.meta.get_field(fieldname)
		if fieldname not in EDITABLE_FIELDS or not df:
			frappe.throw(_("You cannot edit field {0} on this Shift Assignment.").format(fieldname), frappe.PermissionError)
		if df.permlevel and frappe.session.user != "Administrator" and df.permlevel not in write_levels:
			frappe.throw(_("You cannot edit field {0} on this Shift Assignment.").format(fieldname), frappe.PermissionError)
		if value is not None and not isinstance(value, str):
			frappe.throw(_("Invalid value for Shift Assignment field {0}.").format(fieldname))

	changed_links = [
		field for field in ("employee", "shift_type", "custom_project")
		if field in values and (values[field] or "") != (doc.get(field) or "")
	]
	for fieldname, value in values.items():
		if fieldname in ("start_date", "end_date"):
			value = getdate(value) if value else None
		doc.set(fieldname, value)
	if not all(doc.get(field) for field in ("employee", "shift_type", "start_date")):
		frappe.throw(_("Employee, Shift Type and Start Date are required."))
	if doc.status not in ("Active", "Inactive"):
		frappe.throw(_("Shift Assignment status must be Active or Inactive."))
	_refresh_link_details(doc, changed_links)

	if doc.docstatus == 1:
		# Only this endpoint's explicit editor fields (and their fetched details)
		# bypass allow_on_submit. Keep normal permissions, link checks, hooks,
		# versions and HRMS validation; never write allocation fields with db_set.
		doc.flags.ignore_validate_update_after_submit = True
		doc.run_method("validate")
	doc.save(ignore_version=False)
	return {"name": doc.name}
