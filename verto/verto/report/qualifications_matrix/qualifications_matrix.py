"""Employee qualifications matrix backed by Employee qualification child rows."""

from __future__ import annotations

from hashlib import sha1

import frappe
from frappe import _
from frappe.utils import formatdate

from verto.api.qualifications import calculate_validity_status


QUALIFICATION_CHILD_DOCTYPE = "Employee Qualification Item"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	employees = _get_employees(filters)
	if not employees:
		return _base_columns(), []

	all_skills = _get_qualification_skills(filters)
	requirements = _get_designation_requirements(employees, set(all_skills))
	records = _get_employee_qualifications(employees, all_skills)
	visible_skills = _get_visible_skills(filters, all_skills, requirements, records)

	columns = _base_columns() + [_qualification_column(skill) for skill in visible_skills]
	data = []

	for employee in employees:
		row = {
			"employee": employee.name,
			"employee_name": employee.employee_name,
			"department": employee.department,
			"designation": employee.designation,
		}
		required_skills = requirements.get(employee.designation, set())
		states = {}

		for skill in visible_skills:
			fieldname = _skill_fieldname(skill.name)
			record = records.get((employee.name, skill.name))
			is_required = skill.name in required_skills
			state = _get_cell_state(record, skill, is_required)
			states[skill.name] = state
			row[fieldname] = state
			row[f"{fieldname}__details"] = _get_cell_details(record, skill, is_required)

		row["compliance_status"] = _get_compliance_status(required_skills, states)
		if _matches_compliance_filter(row["compliance_status"], filters.get("compliance_status")):
			data.append(row)

	return columns, data


def _base_columns():
	return [
		{
			"fieldname": "employee",
			"label": _("Employee ID"),
			"fieldtype": "Link",
			"options": "Employee",
			"width": 115,
		},
		{"fieldname": "employee_name", "label": _("Employee"), "fieldtype": "Data", "width": 180},
		{
			"fieldname": "department",
			"label": _("Department"),
			"fieldtype": "Link",
			"options": "Department",
			"width": 140,
		},
		{
			"fieldname": "designation",
			"label": _("Designation"),
			"fieldtype": "Link",
			"options": "Designation",
			"width": 140,
		},
		{
			"fieldname": "compliance_status",
			"label": _("Overall Status"),
			"fieldtype": "Data",
			"width": 145,
		},
	]


def _get_employees(filters):
	employee_filters = {}
	for fieldname in ("company", "department", "designation", "employee"):
		if filters.get(fieldname):
			employee_filters[fieldname if fieldname != "employee" else "name"] = filters[fieldname]

	if filters.get("employee_status"):
		employee_filters["status"] = filters.employee_status

	return frappe.get_all(
		"Employee",
		filters=employee_filters,
		fields=["name", "employee_name", "company", "department", "designation", "status"],
		order_by="employee_name asc",
	)


def _get_qualification_skills(filters):
	skill_filters = {"is_qualification": 1}
	if filters.get("qualification_category"):
		skill_filters["qualification_category"] = filters.qualification_category

	return {
		row.name: row
		for row in frappe.get_all(
			"Skill",
			filters=skill_filters,
			fields=[
				"name",
				"skill_name",
				"qualification_category",
				"requires_evidence",
				"has_expiry",
				"expiry_warning_days",
			],
			order_by="skill_name asc",
		)
	}


def _get_designation_requirements(employees, qualification_names):
	designations = sorted({employee.designation for employee in employees if employee.designation})
	if not designations or not qualification_names:
		return {}

	requirements = {}
	for row in frappe.get_all(
		"Designation Skill",
		filters={
			"parent": ["in", designations],
			"parenttype": "Designation",
			"skill": ["in", sorted(qualification_names)],
		},
		fields=["parent", "skill"],
	):
		requirements.setdefault(row.parent, set()).add(row.skill)
	return requirements


def _get_employee_qualifications(employees, skills):
	if not skills or not frappe.db.exists("DocType", QUALIFICATION_CHILD_DOCTYPE):
		return {}

	rows = frappe.get_all(
		QUALIFICATION_CHILD_DOCTYPE,
		filters={
			"parent": ["in", [employee.name for employee in employees]],
			"parenttype": "Employee",
			"is_current": 1,
			"qualification": ["in", sorted(skills)],
		},
		fields=[
			"name",
			"parent",
			"idx",
			"qualification",
			"certificate_number",
			"issuing_authority",
			"issue_date",
			"expiry_date",
			"does_not_expire",
			"evidence",
			"verification_status",
			"validity_status",
		],
		order_by="parent asc, qualification asc, idx desc",
	)

	records = {}
	for row in rows:
		records.setdefault((row.parent, row.qualification), row)
	return records


def _get_visible_skills(filters, all_skills, requirements, records):
	if filters.get("qualification_scope") == "All Qualifications":
		visible_names = set(all_skills)
	else:
		visible_names = {skill for required in requirements.values() for skill in required}
		visible_names.update(skill for _employee, skill in records)

	return sorted(
		(all_skills[name] for name in visible_names if name in all_skills),
		key=lambda skill: (skill.skill_name or skill.name).lower(),
	)


def _qualification_column(skill):
	return {
		"fieldname": _skill_fieldname(skill.name),
		"label": skill.skill_name or skill.name,
		"fieldtype": "Data",
		"width": 145,
	}


def _skill_fieldname(skill_name):
	return f"qualification_{sha1(skill_name.encode('utf-8')).hexdigest()[:10]}"


def _get_cell_state(record, skill, is_required):
	if not record:
		return "Missing" if is_required else ""

	if record.verification_status == "Rejected":
		return "Rejected"
	if record.verification_status != "Verified":
		return "Pending Verification"

	return calculate_validity_status(
		is_current=True,
		does_not_expire=bool(record.does_not_expire),
		has_expiry=bool(skill.has_expiry),
		expiry_date=record.expiry_date,
		warning_days=skill.expiry_warning_days,
	) or "Incomplete"


def _get_cell_details(record, skill, is_required):
	details = [skill.skill_name or skill.name]
	details.append(_("Required") if is_required else _("Not required by designation"))
	if not record:
		return " · ".join(details)

	if record.certificate_number:
		details.append(_("Certificate: {0}").format(record.certificate_number))
	if record.issuing_authority:
		details.append(_("Issued by: {0}").format(record.issuing_authority))
	if record.expiry_date:
		details.append(_("Expires: {0}").format(formatdate(record.expiry_date)))
	elif record.does_not_expire or not skill.has_expiry:
		details.append(_("Does not expire"))
	if record.evidence:
		details.append(_("Evidence attached"))
	return " · ".join(details)


def _get_compliance_status(required_skills, states):
	if not required_skills:
		return "No Requirements"

	required_states = [states.get(skill, "Missing") for skill in required_skills]
	if any(state in {"Missing", "Expired", "Rejected", "Incomplete"} for state in required_states):
		return "Non-compliant"
	if any(state in {"Expiring Soon", "Pending Verification"} for state in required_states):
		return "Attention Required"
	return "Compliant"


def _matches_compliance_filter(status, selected_status):
	return not selected_status or selected_status == status
