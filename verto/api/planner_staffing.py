"""Project staffing requirements and the role held on a project shift."""

import frappe
from frappe import _
from frappe.utils import getdate

REQUIREMENTS_FIELD = "custom_personnel_requirements"
DESIGNATION_FIELD = "custom_project_designation"
REQUIREMENT_DOCTYPE = "Project Personnel Requirement"
MAX_REQUIREMENTS = 100


def ensure_staffing_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({
		"Project": [
			{"fieldname": "custom_personnel_tab", "fieldtype": "Tab Break", "label": "Personnel", "insert_after": "users"},
			{"fieldname": REQUIREMENTS_FIELD, "fieldtype": "Table", "label": "Personnel Requirements",
			 "options": REQUIREMENT_DOCTYPE, "insert_after": "custom_personnel_tab"},
		],
		"Shift Assignment": [{"fieldname": DESIGNATION_FIELD, "fieldtype": "Link", "label": "Project Designation",
			"options": "Designation", "insert_after": "custom_project", "allow_on_submit": 1,
			"description": "The role allocated on this project."}],
		"Shift Schedule Assignment": [
			{"fieldname": "custom_project", "fieldtype": "Link", "label": "Project", "options": "Project", "insert_after": "shift_location"},
			{"fieldname": DESIGNATION_FIELD, "fieldtype": "Link", "label": "Project Designation",
			 "options": "Designation", "insert_after": "custom_project"},
		],
	}, update=False)
	return True


def normalise_requirements(rows):
	if isinstance(rows, str):
		rows = frappe.parse_json(rows)
	if not isinstance(rows, list) or len(rows) > MAX_REQUIREMENTS:
		frappe.throw(_("Supply a personnel requirements table with at most {0} rows.").format(MAX_REQUIREMENTS))
	result, seen = [], set()
	for row in rows:
		if not isinstance(row, dict):
			frappe.throw(_("Invalid personnel requirement row."))
		shift = str(row.get("shift") or "").strip().upper()
		designation = str(row.get("designation") or "").strip()
		if shift not in ("DS", "NS"):
			frappe.throw(_("Personnel requirements must use DS or NS."))
		try:
			required = int(str(row.get("required_personnel") or 0))
		except (ValueError, TypeError, OverflowError):
			frappe.throw(_("Required Personnel must be a non-negative whole number."))
		if required < 0:
			frappe.throw(_("Required Personnel cannot be negative."))
		key = (shift, designation.casefold())
		if key in seen:
			frappe.throw(_("Each shift and designation can appear only once in Personnel Requirements."))
		seen.add(key)
		result.append({"shift": shift, "designation": designation or None, "required_personnel": required})
	if result:
		names = {row["designation"] for row in result if row["designation"]}
		if names:
			existing = set(frappe.get_all("Designation", filters={"name": ["in", sorted(names)]}, pluck="name"))
			if names - existing:
				frappe.throw(_("Designation {0} does not exist.").format(", ".join(sorted(names - existing))))
	return result


def requirement_totals(rows):
	return {shift: sum(int(row.get("required_personnel") or 0) for row in rows if row.get("shift") == shift)
		for shift in ("DS", "NS")}


def validate_project_staffing(doc, method=None):
	if not doc.meta.has_field(REQUIREMENTS_FIELD):
		return
	previous = doc.get_doc_before_save()
	if not doc.get(REQUIREMENTS_FIELD) and not (previous and previous.get(REQUIREMENTS_FIELD)):
		return
	children = doc.get(REQUIREMENTS_FIELD) or []
	rows = normalise_requirements([row.as_dict() for row in children])
	for original, normalised in zip(children, rows, strict=True):
		original.update(normalised)
	from verto.api.planner import _project_planner_edit_fields
	fields, totals = _project_planner_edit_fields(), requirement_totals(rows)
	for shift, key in (("DS", "ds_field"), ("NS", "ns_field")):
		if fields.get(key):
			doc.set(fields[key], totals[shift])


def validate_designation(project, designation):
	designation = str(designation or "").strip()
	if not designation:
		return None
	if not project:
		frappe.throw(_("Select a Project before assigning a project designation."))
	if not frappe.get_meta("Shift Assignment").has_field(DESIGNATION_FIELD):
		frappe.throw(_("Project staffing fields are not installed. Run the site migration."))
	if not frappe.db.exists("Designation", designation):
		frappe.throw(_("Designation {0} does not exist.").format(designation))
	return designation


def apply_scheduled_staffing(doc, method=None):
	# HRMS also creates future recurring shifts outside the Planner endpoint.
	if doc.is_new() and doc.get("shift_schedule_assignment"):
		schedule = frappe.get_doc("Shift Schedule Assignment", doc.shift_schedule_assignment)
		if schedule.get("custom_project") and not doc.get("custom_project"):
			doc.set("custom_project", schedule.custom_project)
		if schedule.get(DESIGNATION_FIELD) and not doc.get(DESIGNATION_FIELD):
			doc.set(DESIGNATION_FIELD, schedule.get(DESIGNATION_FIELD))
	if doc.meta.has_field(DESIGNATION_FIELD):
		doc.set(DESIGNATION_FIELD, validate_designation(doc.get("custom_project"), doc.get(DESIGNATION_FIELD)))


def get_project_requirements(project_names):
	if not project_names or not frappe.get_meta("Project").has_field(REQUIREMENTS_FIELD):
		return {}
	result = {}
	for row in frappe.get_all(REQUIREMENT_DOCTYPE,
		filters={"parent": ["in", list(project_names)], "parenttype": "Project", "parentfield": REQUIREMENTS_FIELD},
		fields=["parent", "shift", "designation", "required_personnel"], order_by="idx asc",
		limit_page_length=len(project_names) * MAX_REQUIREMENTS):
		result.setdefault(row.parent, []).append({key: row.get(key) for key in ("shift", "designation", "required_personnel")})
	return result


def summarise_staffing(shifts, requirements=None):
	from verto.api.planner import _is_ds_personnel_shift, _is_ns_personnel_shift
	groups = {}
	def group(shift, designation):
		return groups.setdefault((shift, designation), {"shift": shift, "designation": designation,
			"required_personnel": 0, "_personnel": {}})
	for row in requirements or []:
		group(row["shift"], row.get("designation") or "")["required_personnel"] = int(row.get("required_personnel") or 0)
	for row in shifts:
		if row.get("docstatus", 1) != 1 or row.get("status", "Active") != "Active" or not row.get("employee"):
			continue
		shift_type = row.get("shift_type")
		shift = "DS" if _is_ds_personnel_shift(shift_type) else ("NS" if _is_ns_personnel_shift(shift_type) else None)
		if shift:
			group(shift, row.get(DESIGNATION_FIELD) or "")["_personnel"][row["employee"]] = {
				"employee": row["employee"], "employee_name": row.get("employee_name") or row["employee"]}
	result = []
	for row in groups.values():
		row["personnel"] = sorted(row.pop("_personnel").values(), key=lambda person: (person["employee_name"].casefold(), person["employee"]))
		result.append(row)
	return sorted(result, key=lambda row: (row["shift"], row["designation"].casefold()))


def project_staffing_details(doc, ds_requested=0, ns_requested=0):
	if not doc.meta.has_field(REQUIREMENTS_FIELD):
		return {"personnel_requirements": [], "personnel_allocations": [], "can_update_personnel_requirements": False}
	rows = [{key: row.get(key) for key in ("shift", "designation", "required_personnel")}
		for row in (doc.get(REQUIREMENTS_FIELD) or [])]
	filters = {"custom_project": doc.name, "docstatus": 1, "status": "Active"}
	start, end = doc.get("expected_start_date"), doc.get("expected_end_date")
	if end:
		filters["start_date"] = ["<=", end]
	fields = ["employee", "employee_name", "shift_type", "start_date", "end_date"]
	if frappe.get_meta("Shift Assignment").has_field(DESIGNATION_FIELD):
		fields.append(DESIGNATION_FIELD)
	shifts = frappe.get_all("Shift Assignment", filters=filters, fields=fields, limit_page_length=10000)
	if start:
		shifts = [row for row in shifts if not row.get("end_date") or getdate(row["end_date"]) >= getdate(start)]
	requirements = rows or [{"shift": shift, "designation": "", "required_personnel": required}
		for shift, required in (("DS", ds_requested), ("NS", ns_requested))]
	totals = requirement_totals(rows)
	return {**({"ds_requested": totals["DS"], "ns_requested": totals["NS"]} if rows else {}),
		"personnel_requirements": rows, "personnel_allocations": summarise_staffing(shifts, requirements),
		"can_update_personnel_requirements": bool(doc.meta.has_field(REQUIREMENTS_FIELD) and doc.has_permission("write"))}
