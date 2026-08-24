"""Qualification validation and expiry maintenance for Employee records."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	add_months,
	cint,
	cstr,
	date_diff,
	formatdate,
	getdate,
	now_datetime,
	today,
)


QUALIFICATIONS_FIELD = "qualifications"
QUALIFICATION_CHILD_DOCTYPE = "Employee Qualification Item"
QUALIFICATION_REMINDER_DAYS = (60, 30, 7, 0)
QUALIFICATION_NOTIFICATION_URL = "/verto-mobile"


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


def send_qualification_expiry_notifications(target_date=None, dry_run=False):
	"""Send milestone reminders for verified employee qualifications.

	The default milestones are 60, 30 and 7 days before expiry, plus the
	expiry date. A Skill's configured warning period replaces the default
	60-day milestone when it differs. ``target_date`` and ``dry_run`` make the
	job safe to verify with ``bench execute`` before enabling live delivery.
	"""
	target_date = getdate(target_date or today())
	dry_run = bool(cint(dry_run))
	candidates = _get_expiry_candidates(target_date)
	notification_count = 0
	push_recipient_count = 0
	queued_push_count = 0

	for candidate in candidates:
		new_recipients = []
		for user in candidate["recipients"]:
			if _qualification_notification_exists(candidate, user):
				continue
			if not dry_run:
				_create_qualification_notification_log(candidate, user)
			new_recipients.append(user)

		notification_count += len(new_recipients)
		push_recipient_count += len(new_recipients)

		if new_recipients and not dry_run:
			from verto.api.mobile.push_notifications import queue_push_to_users

			queue_push_to_users(
				new_recipients,
				{
					"title": candidate["title"],
					"body": candidate["message"],
					"url": QUALIFICATION_NOTIFICATION_URL,
					"tag": f"qualification-expiry-{candidate['row_name']}-{candidate['days_left']}",
				},
				notification_type="qualification_expiry",
			)
			# enqueue_after_commit may intentionally return None while the transaction
			# is open, even though the job has been registered for delivery.
			queued_push_count += 1

	return {
		"date": target_date.isoformat(),
		"candidate_count": len(candidates),
		"notification_count": notification_count,
		"push_recipient_count": push_recipient_count,
		"queued_push_count": queued_push_count,
		"dry_run": dry_run,
		"candidates": [
			{
				"employee": candidate["employee"],
				"employee_name": candidate["employee_name"],
				"qualification": candidate["qualification"],
				"expiry_date": candidate["expiry_date"].isoformat(),
				"days_left": candidate["days_left"],
				"recipients": candidate["recipients"],
			}
			for candidate in candidates
		],
	}


def _get_expiry_candidates(target_date):
	if not frappe.db.exists("DocType", QUALIFICATION_CHILD_DOCTYPE):
		return []

	rows = frappe.get_all(
		QUALIFICATION_CHILD_DOCTYPE,
		filters={
			"parenttype": "Employee",
			"is_current": 1,
			"verification_status": "Verified",
			"does_not_expire": 0,
			"expiry_date": ["is", "set"],
		},
		fields=["name", "parent", "qualification", "expiry_date"],
	)
	if not rows:
		return []

	rules_by_skill = _get_rules(row.qualification for row in rows if row.qualification)
	employees = _get_notification_employees(row.parent for row in rows if row.parent)
	supervisor_users = _get_supervisor_users(employees.values())
	hr_users = _get_hr_manager_users()
	candidates = []

	for row in rows:
		rules = rules_by_skill.get(row.qualification)
		employee = employees.get(row.parent)
		if not rules or not rules.is_qualification or not rules.has_expiry or not employee:
			continue

		expiry_date = getdate(row.expiry_date)
		days_left = date_diff(expiry_date, target_date)
		if days_left not in _get_reminder_days(rules.expiry_warning_days):
			continue

		recipients = _enabled_users(
			[
				employee.user_id,
				supervisor_users.get(employee.reports_to),
				*hr_users,
			]
		)
		if not recipients:
			continue

		title, message = _get_expiry_message(
			employee.employee_name,
			row.qualification,
			expiry_date,
			days_left,
		)
		candidates.append(
			{
				"row_name": row.name,
				"employee": employee.name,
				"employee_name": employee.employee_name,
				"qualification": row.qualification,
				"expiry_date": expiry_date,
				"days_left": days_left,
				"recipients": recipients,
				"title": title,
				"message": message,
				"link": f"/app/employee/{quote(employee.name, safe='')}",
			}
		)

	return candidates


def _get_notification_employees(employee_names):
	names = sorted({name for name in employee_names if name})
	if not names:
		return {}
	return {
		row.name: row
		for row in frappe.get_all(
			"Employee",
			filters={"name": ["in", names], "status": "Active"},
			fields=["name", "employee_name", "user_id", "reports_to"],
		)
	}


def _get_supervisor_users(employees):
	supervisor_names = sorted({employee.reports_to for employee in employees if employee.reports_to})
	if not supervisor_names:
		return {}
	return {
		row.name: row.user_id
		for row in frappe.get_all(
			"Employee",
			filters={"name": ["in", supervisor_names], "status": "Active"},
			fields=["name", "user_id"],
		)
		if row.user_id
	}


def _get_hr_manager_users():
	return frappe.get_all(
		"Has Role",
		filters={"parenttype": "User", "role": "HR Manager"},
		pluck="parent",
	)


def _enabled_users(users):
	users = sorted({user for user in users if user and user != "Guest"})
	if not users:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ["in", users], "enabled": 1},
		pluck="name",
		order_by="name asc",
	)


def _get_reminder_days(warning_days):
	configured_warning = max(cint(warning_days), 0)
	days = set(QUALIFICATION_REMINDER_DAYS)
	if configured_warning and configured_warning != QUALIFICATION_REMINDER_DAYS[0]:
		days.discard(QUALIFICATION_REMINDER_DAYS[0])
		days.add(configured_warning)
	return days


def _get_expiry_message(employee_name, qualification, expiry_date, days_left):
	formatted_expiry = formatdate(expiry_date)
	if days_left == 0:
		title = _("Qualification expires today")
		message = _("{0}'s {1} qualification expires today ({2}).").format(
			employee_name,
			qualification,
			formatted_expiry,
		)
	else:
		title = _("Qualification expires in {0} days").format(days_left)
		message = _("{0}'s {1} qualification expires on {2}.").format(
			employee_name,
			qualification,
			formatted_expiry,
		)
	return title, message


def _qualification_notification_exists(candidate, user):
	meta = frappe.get_meta("Notification Log")
	title_field = "title" if meta.has_field("title") else "subject"
	return bool(
		frappe.db.exists(
			"Notification Log",
			{
				"for_user": user,
				"document_type": "Employee",
				"document_name": candidate["employee"],
				title_field: _notification_dedupe_title(candidate),
			},
		)
	)


def _notification_dedupe_title(candidate):
	return f"{candidate['title']}: {candidate['qualification']} ({candidate['expiry_date'].isoformat()})"


def _create_qualification_notification_log(candidate, user):
	meta = frappe.get_meta("Notification Log")
	notification = frappe.new_doc("Notification Log")
	dedupe_title = _notification_dedupe_title(candidate)

	notification.for_user = user
	notification.from_user = "Administrator"
	notification.document_type = "Employee"
	notification.document_name = candidate["employee"]
	notification.read = 0
	if meta.has_field("title"):
		notification.title = dedupe_title
	if meta.has_field("subject"):
		notification.subject = dedupe_title
	if meta.has_field("description"):
		notification.description = candidate["message"]
	if meta.has_field("email_content"):
		notification.email_content = candidate["message"]
	if meta.has_field("link"):
		notification.link = candidate["link"]

	notification.insert(ignore_permissions=True)


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
	return any(
		_normalize_audited_value(fieldname, row.get(fieldname))
		!= _normalize_audited_value(fieldname, previous_row.get(fieldname))
		for fieldname in audited_fields
	)


def _normalize_audited_value(fieldname, value):
	"""Normalize equivalent form and database values before audit comparison."""
	if fieldname == "does_not_expire":
		return cint(value)
	if fieldname in {"issue_date", "expiry_date"}:
		return getdate(value) if value else None
	return cstr(value or "")


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
