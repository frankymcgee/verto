"""Qualification validation and expiry maintenance for Employee records."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils import add_days, add_months, getdate, now_datetime, today


QUALIFICATIONS_FIELD = "qualifications"
QUALIFICATION_CHILD_DOCTYPE = "Employee Qualification Item"


@dataclass(frozen=True)
class QualificationRules:
	"""Rules inherited from a qualification-enabled Skill."""

	name: str
	is_qualification: bool
	category: str | None
	requires_evidence: bool
	has_expiry: bool
	default_validity_months: int
	expiry_warning_days: int


def calculate_validity_status(
	*,
	is_current: bool,
	does_not_expire: bool,
	has_expiry: bool,
	expiry_date=None,
	warning_days: int = 60,
	reference_date=None,
) -> str:
	"""Return the stored validity status for one employee qualification row."""
	if not is_current:
		return "Superseded"

	if does_not_expire or not has_expiry:
		return "Valid"

	if not expiry_date:
		return ""

	reference_date = getdate(reference_date or today())
	expiry_date = getdate(expiry_date)
	warning_days = max(int(warning_days or 0), 0)

	if expiry_date < reference_date:
		return "Expired"
	if expiry_date <= getdate(add_days(reference_date, warning_days)):
		return "Expiring Soon"
	return "Valid"


def validate_employee_qualifications(doc, method=None):
	"""Validate and enrich the qualification rows stored on an Employee."""
	if not doc.meta.has_field(QUALIFICATIONS_FIELD):
		return

	rows = doc.get(QUALIFICATIONS_FIELD) or []
	if not rows:
		return

	rules_by_skill = _get_rules(row.qualification for row in rows if row.qualification)
	before_rows = _get_previous_rows(doc)
	current_rows = defaultdict(list)

	for row in rows:
		if not row.qualification:
			continue

		rules = rules_by_skill.get(row.qualification)
		if not rules or not rules.is_qualification:
			frappe.throw(
				_("{0} is not enabled as a qualification in Skill.").format(
					frappe.bold(row.qualification)
				),
				title=_("Invalid Qualification"),
			)

		row.qualification_category = rules.category
		_apply_expiry_defaults(row, rules)
		if not row.verification_status:
			row.verification_status = "Pending Verification"
		_apply_verification_audit(row, before_rows.get(row.name), rules)
		row.validity_status = calculate_validity_status(
			is_current=bool(row.is_current),
			does_not_expire=bool(row.does_not_expire),
			has_expiry=rules.has_expiry,
			expiry_date=row.expiry_date,
			warning_days=rules.expiry_warning_days,
		)

		if row.is_current:
			current_rows[row.qualification].append(row)

	_validate_one_current_record(current_rows)


def refresh_qualification_statuses():
	"""Daily scheduler task to refresh statuses without editing Employee records."""
	if not frappe.db.exists("DocType", QUALIFICATION_CHILD_DOCTYPE):
		return {"checked": 0, "updated": 0}

	rows = frappe.get_all(
		QUALIFICATION_CHILD_DOCTYPE,
		fields=[
			"name",
			"qualification",
			"expiry_date",
			"does_not_expire",
			"is_current",
			"validity_status",
		],
	)
	rules_by_skill = _get_rules(row.qualification for row in rows if row.qualification)
	updated = 0

	for row in rows:
		rules = rules_by_skill.get(row.qualification)
		if not rules:
			continue

		status = calculate_validity_status(
			is_current=bool(row.is_current),
			does_not_expire=bool(row.does_not_expire),
			has_expiry=rules.has_expiry,
			expiry_date=row.expiry_date,
			warning_days=rules.expiry_warning_days,
		)
		if status == (row.validity_status or ""):
			continue

		frappe.db.set_value(
			QUALIFICATION_CHILD_DOCTYPE,
			row.name,
			"validity_status",
			status,
			update_modified=False,
		)
		updated += 1

	return {"checked": len(rows), "updated": updated}


def _get_rules(skill_names) -> dict[str, QualificationRules]:
	names = sorted({name for name in skill_names if name})
	if not names:
		return {}

	return {
		row.name: QualificationRules(
			name=row.name,
			is_qualification=bool(row.is_qualification),
			category=row.qualification_category,
			requires_evidence=bool(row.requires_evidence),
			has_expiry=bool(row.has_expiry),
			default_validity_months=max(int(row.default_validity_months or 0), 0),
			expiry_warning_days=max(int(row.expiry_warning_days or 0), 0),
		)
		for row in frappe.get_all(
			"Skill",
			filters={"name": ["in", names]},
			fields=[
				"name",
				"is_qualification",
				"qualification_category",
				"requires_evidence",
				"has_expiry",
				"default_validity_months",
				"expiry_warning_days",
			],
		)
	}


def _apply_expiry_defaults(row, rules: QualificationRules):
	if not rules.has_expiry:
		row.does_not_expire = 1
		row.expiry_date = None
		return

	if row.does_not_expire:
		row.expiry_date = None
		return

	if row.issue_date and not row.expiry_date and rules.default_validity_months:
		row.expiry_date = getdate(add_months(row.issue_date, rules.default_validity_months))


def _apply_verification_audit(row, previous_row, rules: QualificationRules):
	previous_status = previous_row.verification_status if previous_row else None
	current_status = row.verification_status

	if previous_status == "Verified" and _verification_details_changed(row, previous_row):
		row.verification_status = "Pending Verification"
		row.verified_by = None
		row.verified_on = None
		return

	if current_status == "Verified":
		if rules.requires_evidence and not row.evidence:
			frappe.throw(
				_("Evidence is required before {0} can be verified.").format(
					frappe.bold(row.qualification)
				),
				title=_("Qualification Evidence Required"),
			)
		if rules.has_expiry and not row.does_not_expire and not row.expiry_date:
			frappe.throw(
				_("An expiry date is required before {0} can be verified.").format(
					frappe.bold(row.qualification)
				),
				title=_("Qualification Expiry Required"),
			)

		if previous_status != "Verified" or not row.verified_by or not row.verified_on:
			row.verified_by = frappe.session.user
			row.verified_on = now_datetime()
	else:
		row.verified_by = None
		row.verified_on = None


def _verification_details_changed(row, previous_row) -> bool:
	if not previous_row:
		return False

	audited_fields = (
		"qualification",
		"certificate_number",
		"issuing_authority",
		"issue_date",
		"expiry_date",
		"does_not_expire",
		"evidence",
	)
	return any(row.get(fieldname) != previous_row.get(fieldname) for fieldname in audited_fields)


def _get_previous_rows(doc):
	previous_doc = doc.get_doc_before_save()
	if not previous_doc or not previous_doc.meta.has_field(QUALIFICATIONS_FIELD):
		return {}
	return {row.name: row for row in previous_doc.get(QUALIFICATIONS_FIELD) or [] if row.name}


def _validate_one_current_record(current_rows):
	duplicates = [qualification for qualification, rows in current_rows.items() if len(rows) > 1]
	if not duplicates:
		return

	frappe.throw(
		_("Only one current record is allowed for each qualification. Update the older row to Superseded: {0}").format(
			", ".join(frappe.bold(qualification) for qualification in sorted(duplicates))
		),
		title=_("Duplicate Current Qualifications"),
	)
