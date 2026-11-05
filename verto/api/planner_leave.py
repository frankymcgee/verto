"""Permission-aware viewing and editing of leave from the Planner."""

import frappe
from frappe import _
from frappe.model.workflow import (
	apply_workflow, get_transitions, get_workflow, get_workflow_name, has_approval_access,
)

from verto.api.planner import (
	EVENT_LAYOUT_FIELD_TYPES,
	LEAVE_APPLICATION_CREATE_ALLOWED_FIELD_TYPES,
	_leave_application_create_field_to_dict,
	_leave_status,
	_normalise_leave_application_create_value,
)


def _workflow(doc):
	return get_workflow(doc.doctype) if get_workflow_name(doc.doctype) else None


def _can_edit(doc, workflow):
	if doc.docstatus == 2 or not doc.has_permission("write"):
		return False
	if workflow and frappe.session.user != "Administrator":
		state = next((row for row in workflow.states if row.state == doc.get(workflow.workflow_state_field)), None)
		return bool(state and state.allow_edit in frappe.get_roles())
	return True


def _fields(doc, workflow):
	admin = frappe.session.user == "Administrator"
	read_levels = set(doc.get_permlevel_access("read"))
	write_levels = set(doc.get_permlevel_access("write"))
	can_edit = _can_edit(doc, workflow)
	can_submit = doc.has_permission("submit")
	fields = []
	for df in doc.meta.fields:
		if not df.fieldtype or df.hidden or df.fieldtype == "Password":
			continue
		if df.permlevel and not admin and df.permlevel not in read_levels:
			continue
		field = _leave_application_create_field_to_dict(df)
		field["read_only_depends_on"] = df.get("read_only_depends_on")
		field["mandatory_depends_on"] = df.get("mandatory_depends_on")
		field["read_only"] = bool(
			df.read_only or not can_edit
			or (df.permlevel and not admin and df.permlevel not in write_levels)
			or (doc.docstatus == 1 and not df.allow_on_submit)
			or df.get("set_only_once")
			or (df.get("mask") and not doc.has_permission("mask"))
			or (df.fieldname == "status" and (workflow or not can_submit or doc.docstatus != 0))
			or (workflow and df.fieldname == workflow.workflow_state_field)
		)
		fields.append(field)
	return fields


def _editable_fields(doc, workflow):
	return {
		field["fieldname"]: doc.meta.get_field(field["fieldname"])
		for field in _fields(doc, workflow)
		if not field["read_only"] and field["fieldtype"] in LEAVE_APPLICATION_CREATE_ALLOWED_FIELD_TYPES
	}


def check_link_field_permission(name, fieldname, link_doctype):
	doc = frappe.get_doc("Leave Application", name)
	doc.check_permission("read")
	df = _editable_fields(doc, _workflow(doc)).get(fieldname)
	if not df or df.fieldtype not in ("Link", "Dynamic Link"):
		frappe.throw(_("You cannot edit this Leave Application field."), frappe.PermissionError)
	target = df.options if df.fieldtype == "Link" else doc.get(df.options)
	if target != link_doctype:
		frappe.throw(_("Invalid linked DocType for this field."), frappe.PermissionError)


@frappe.whitelist()
def get_details(name: str) -> dict:
	doc = frappe.get_doc("Leave Application", name)
	doc.check_permission("read")
	workflow = _workflow(doc)
	fields = _fields(doc, workflow)
	actions = []
	if workflow and doc.docstatus != 2:
		actions = list(dict.fromkeys(
			row.action for row in get_transitions(doc, workflow)
			if has_approval_access(frappe.session.user, doc, row)
		))
	response = {
		"doctype": doc.doctype,
		"name": doc.name,
		"modified": str(doc.modified),
		"docstatus": int(doc.docstatus),
		"status": _leave_status({"docstatus": doc.docstatus, "status": doc.get("status")}),
		"fields": fields,
		"can_write": bool(_editable_fields(doc, workflow)),
		"can_submit": bool(not workflow and doc.docstatus == 0 and _can_edit(doc, workflow) and doc.has_permission("submit")),
		"can_cancel": bool(not workflow and doc.docstatus == 1 and doc.has_permission("cancel")),
		"workflow_actions": actions,
	}
	doc.apply_fieldlevel_read_permissions()
	response["values"] = {
		field["fieldname"]: doc.get(field["fieldname"])
		for field in fields
		if field["fieldname"] and field["fieldtype"] not in EVENT_LAYOUT_FIELD_TYPES
		and not field["unsupported"]
	}
	return response


@frappe.whitelist(methods=["POST"])
def update(name: str, expected_modified: str | None = None, values=None, action: str = "save", workflow_action: str | None = None):
	# Lock while checking the revision and applying document/workflow actions.
	doc = frappe.get_doc("Leave Application", name, for_update=True)
	doc.check_permission("read")
	if not expected_modified or str(doc.modified) != str(expected_modified):
		frappe.throw(_("This Leave Application changed elsewhere. Reload it before saving."), frappe.TimestampMismatchError)
	if doc.docstatus == 2:
		frappe.throw(_("Cancelled Leave Applications are read-only."))
	if action not in ("save", "submit", "cancel", "workflow"):
		frappe.throw(_("Invalid Leave Application action."))
	workflow = _workflow(doc)
	if workflow and action in ("submit", "cancel"):
		frappe.throw(_("Use an available workflow action for this Leave Application."))
	if action == "cancel":
		if doc.docstatus != 1:
			frappe.throw(_("Only submitted Leave Applications can be cancelled."))
		doc.check_permission("cancel")
		doc.cancel()
		return {"name": doc.name}

	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if not isinstance(values, dict):
		frappe.throw(_("Invalid Leave Application values."))
	allowed = _editable_fields(doc, workflow)
	for fieldname in values:
		if fieldname not in allowed:
			frappe.throw(_("You cannot edit field {0} on this Leave Application.").format(fieldname), frappe.PermissionError)
	if values.get("status") == "Cancelled":
		frappe.throw(_("Use Cancel Leave Application to cancel a submitted request."))
	for fieldname, value in values.items():
		doc.set(fieldname, _normalise_leave_application_create_value(allowed[fieldname], value))
	if "employee" in values:
		employee = frappe.db.get_value("Employee", doc.employee, ["employee_name", "company", "department"], as_dict=True)
		if not employee:
			frappe.throw(_("Employee {0} was not found.").format(doc.employee))
		for fieldname in ("employee_name", "company", "department"):
			doc.set(fieldname, employee.get(fieldname))

	if action == "workflow":
		if not workflow or not workflow_action:
			frappe.throw(_("No workflow action was selected."))
		if values:
			doc.check_permission("write")
			doc.save()
		# Frappe checks transition roles, conditions and self-approval, then invokes
		# the normal save/submit/cancel lifecycle (including HRMS leave ledgers).
		apply_workflow(doc.as_dict(), workflow_action)
	elif action == "submit":
		if doc.docstatus != 0:
			frappe.throw(_("Only draft Leave Applications can be submitted."))
		doc.check_permission("submit")
		doc.submit()
	else:
		if not _can_edit(doc, workflow):
			frappe.throw(_("You cannot edit this Leave Application."), frappe.PermissionError)
		doc.check_permission("write")
		doc.save()
	return {"name": doc.name}
