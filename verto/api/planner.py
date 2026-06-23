import frappe
from frappe import _
from frappe.utils import add_days, date_diff, getdate, get_datetime_str

from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

from hrms.hr.doctype.shift_assignment.shift_assignment import ShiftAssignment
from hrms.hr.doctype.shift_schedule.shift_schedule import get_or_insert_shift_schedule


ANNUAL_ROSTER_RESULT_LIMIT = 1000

def check_app_permission():
	"""Check if user has permission to access the app (for showing the app on app screen)"""
	if frappe.session.user == "Administrator":
		return True

	if frappe.has_permission("Employee", ptype="read"):
		return True

	return False

@frappe.whitelist()
def get_current_user_info():
	user = frappe.get_doc("User", frappe.session.user)

	return {
		"name": user.name,
		"first_name": user.first_name,
		"full_name": user.full_name,
		"user_image": user.user_image,
		"roles": frappe.get_roles(frappe.session.user),
	}


def _doctype_has_field(doctype: str, fieldname: str) -> bool:
	try:
		return frappe.get_meta(doctype).has_field(fieldname)
	except Exception:
		return False


def _set_doc_field_if_exists(doc, fieldname: str, value) -> None:
	if _doctype_has_field(doc.doctype, fieldname):
		doc.set(fieldname, value)


def _get_project_title(project: str | None) -> str | None:
	if not project:
		return None
	return frappe.db.get_value("Project", project, "project_name") or project


def create_planner_shift_assignment(
	employee: str,
	company: str,
	shift_type: str,
	start_date: str,
	end_date: str | None,
	status: str,
	shift_location: str | None = None,
	custom_project: str | None = None,
	shift_schedule_assignment: str | None = None,
	note: str | None = None,
):
	"""Create a Shift Assignment using Planner-owned custom fields.

	Do not call HRMS' create_shift_assignment helper here. The upstream HRMS
	helper only accepts standard HRMS fields, while Planner needs to set custom
	fields like custom_project/custom_project_name before the document is saved
	and submitted.
	"""
	assignment = frappe.new_doc("Shift Assignment")
	assignment.employee = employee
	assignment.company = company
	assignment.shift_type = shift_type
	assignment.start_date = _to_date_str(start_date)
	assignment.end_date = _to_date_str(end_date)
	assignment.status = status
	assignment.shift_location = shift_location

	if shift_schedule_assignment:
		assignment.shift_schedule_assignment = shift_schedule_assignment

	if custom_project:
		_set_doc_field_if_exists(assignment, "custom_project", custom_project)
		_set_doc_field_if_exists(assignment, "custom_project_name", _get_project_title(custom_project))

	if note:
		_set_doc_field_if_exists(assignment, "note", note)

	assignment.save()
	assignment.submit()
	return assignment


def apply_planner_project_to_shift_assignments(
	shift_assignment_names: list[str] | tuple[str, ...] | None = None,
	shift_schedule_assignment: str | None = None,
	custom_project: str | None = None,
	note: str | None = None,
) -> None:
	"""Apply Planner fields to already-created Shift Assignments.

	This is used after HRMS creates shifts from a Shift Schedule Assignment,
	because the upstream schedule code creates standard Shift Assignment records
	and does not know about Planner's custom project/note fields.
	"""
	if not custom_project and not note:
		return

	if shift_assignment_names is None:
		if not shift_schedule_assignment:
			return
		shift_assignment_names = frappe.get_all(
			"Shift Assignment",
			filters={"shift_schedule_assignment": shift_schedule_assignment},
			pluck="name",
			limit_start=0,
			limit_page_length=ANNUAL_ROSTER_RESULT_LIMIT,
			limit=ANNUAL_ROSTER_RESULT_LIMIT,
		)

	project_title = _get_project_title(custom_project) if custom_project else None
	has_custom_project = _doctype_has_field("Shift Assignment", "custom_project")
	has_custom_project_name = _doctype_has_field("Shift Assignment", "custom_project_name")
	has_note = _doctype_has_field("Shift Assignment", "note")

	for shift_assignment in shift_assignment_names or []:
		if custom_project and has_custom_project:
			frappe.db.set_value(
				"Shift Assignment",
				shift_assignment,
				"custom_project",
				custom_project,
				update_modified=False,
			)
		if project_title and has_custom_project_name:
			frappe.db.set_value(
				"Shift Assignment",
				shift_assignment,
				"custom_project_name",
				project_title,
				update_modified=False,
			)
		if note and has_note:
			frappe.db.set_value(
				"Shift Assignment",
				shift_assignment,
				"note",
				note,
				update_modified=False,
			)


def create_shift_schedule_shifts_with_planner_fields(
	shift_schedule_assignment_name: str,
	start_date: str,
	end_date: str | None = None,
	custom_project: str | None = None,
	note: str | None = None,
) -> None:
	shift_schedule_assignment = frappe.get_doc("Shift Schedule Assignment", shift_schedule_assignment_name)
	shift_schedule_assignment.create_shifts(start_date, end_date)

	if custom_project or note:
		apply_planner_project_to_shift_assignments(
			shift_schedule_assignment=shift_schedule_assignment_name,
			custom_project=custom_project,
			note=note,
		)


@frappe.whitelist()
def get_default_company() -> str:
	return frappe.defaults.get_user_default("Company")


@frappe.whitelist()
def get_values(doctype: str, name: str, fields: list) -> dict[str, str]:
	return frappe.db.get_value(doctype, name, fields, as_dict=True)


EVENT_LAYOUT_FIELD_TYPES = {
	"Section Break",
	"Column Break",
	"Tab Break",
}

EVENT_UNSUPPORTED_CREATE_FIELD_TYPES = {
	"Table",
	"Table MultiSelect",
	"HTML",
	"Button",
	"Image",
	"Fold",
	"Geolocation",
	"Signature",
}

EVENT_CREATE_ALLOWED_FIELD_TYPES = {
	"Attach",
	"Attach Image",
	"Check",
	"Code",
	"Color",
	"Currency",
	"Data",
	"Date",
	"Datetime",
	"Dynamic Link",
	"Float",
	"Int",
	"Link",
	"Long Text",
	"Percent",
	"Password",
	"Phone",
	"Rating",
	"Select",
	"Small Text",
	"Text",
	"Text Editor",
	"Time",
}


def _event_field_to_dict(df) -> dict:
	return {
		"fieldname": df.fieldname,
		"fieldtype": df.fieldtype,
		"label": df.label,
		"options": df.options,
		"reqd": df.reqd,
		"default": df.default,
		"depends_on": df.depends_on,
		"description": df.description,
		"read_only": df.read_only,
		"hidden": df.hidden,
		"unsupported": df.fieldtype in EVENT_UNSUPPORTED_CREATE_FIELD_TYPES,
	}


@frappe.whitelist()
def get_event_planner_meta() -> dict:
	"""Return Event fields so the Planner create dialog can build dynamically."""
	if not frappe.has_permission("Event", ptype="create"):
		frappe.throw(_("You do not have permission to create Events."), frappe.PermissionError)

	meta = frappe.get_meta("Event")
	fields = []

	for df in meta.fields:
		if not df.fieldtype:
			continue

		if df.hidden:
			continue

		# Keep layout fields so the dialog follows the Event DocType structure, but
		# skip read-only data fields that cannot be saved from the planner.
		if df.fieldtype not in EVENT_LAYOUT_FIELD_TYPES and df.read_only:
			continue

		fields.append(_event_field_to_dict(df))

	return {
		"doctype": "Event",
		"title": meta.get("title_field") or "subject",
		"fields": fields,
	}


def _event_create_fields_by_name() -> dict:
	meta = frappe.get_meta("Event")
	return {
		df.fieldname: df
		for df in meta.fields
		if df.fieldname
		and not df.hidden
		and not df.read_only
		and df.fieldtype in EVENT_CREATE_ALLOWED_FIELD_TYPES
	}


def _normalise_event_datetime(value, is_end: bool = False):
	if value in (None, ""):
		return None

	text = str(value).strip()
	if not text:
		return None

	text = text.replace("T", " ")
	if len(text) == 10:
		return f"{text} {'23:59:59' if is_end else '00:00:00'}"
	if len(text) == 16:
		return f"{text}:00"
	return text


def _normalise_event_create_value(df, value):
	if value == "":
		return None

	fieldtype = df.fieldtype

	if fieldtype == "Check":
		return 1 if _as_bool(value, default=False) else 0
	if fieldtype == "Int":
		return int(value or 0)
	if fieldtype in ("Float", "Currency", "Percent", "Rating"):
		return float(value or 0)
	if fieldtype == "Datetime":
		return _normalise_event_datetime(value, is_end=df.fieldname == "ends_on")
	if fieldtype == "Date":
		return str(getdate(value)) if value else None

	return value


@frappe.whitelist()
def create_planner_event(values: dict | str | None = None) -> dict:
	"""Create an Event from the dynamically generated Planner Event dialog."""
	if not frappe.has_permission("Event", ptype="create"):
		frappe.throw(_("You do not have permission to create Events."), frappe.PermissionError)

	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if not isinstance(values, dict):
		frappe.throw(_("Invalid Event values."))

	allowed_fields = _event_create_fields_by_name()
	doc = frappe.new_doc("Event")

	# Sensible defaults for the standard Event DocType. These are only applied when
	# the fields exist on the current site and the user has not supplied a value.
	if "event_category" in allowed_fields and not values.get("event_category"):
		values["event_category"] = "Event"
	if "event_type" in allowed_fields and not values.get("event_type"):
		values["event_type"] = "Public"
	if "status" in allowed_fields and not values.get("status"):
		values["status"] = "Open"

	for fieldname, value in values.items():
		df = allowed_fields.get(fieldname)
		if not df:
			continue
		doc.set(fieldname, _normalise_event_create_value(df, value))

	if doc.get("all_day") and doc.get("starts_on") and not doc.get("ends_on"):
		doc.set("ends_on", _normalise_event_datetime(str(doc.get("starts_on"))[:10], is_end=True))

	doc.insert()

	return {
		"name": doc.name,
		"subject": doc.get("subject"),
	}


@frappe.whitelist()
def get_events(
	month_start: str, month_end: str, employee_filters: dict[str, str], shift_filters: dict[str, str]
) -> dict[str, list[dict]]:
	employee_filters = _clean_filters(employee_filters)
	shift_filters = _clean_filters(shift_filters)

	holidays = get_holidays(month_start, month_end, employee_filters)
	leaves = get_leaves(month_start, month_end, employee_filters)
	shifts = get_shifts(month_start, month_end, employee_filters, shift_filters)

	return merge_employee_events(holidays, leaves, shifts)


@frappe.whitelist()
def get_year_events(
	year: str | int, employee_filters: dict[str, str], shift_filters: dict[str, str]
) -> dict:
	"""Return compact annual roster data.

	The annual view keeps project/planning rows and employee rows separate. Employee
	rows still use the same holiday, leave and shift assignment data as the month
	view, while project rows are a compact daily summary by Shift Assignment
	custom_project/custom_project_name.
	"""
	employee_filters = _clean_filters(employee_filters)
	shift_filters = _clean_filters(shift_filters)

	year = int(year)
	year_start = f"{year}-01-01"
	year_end = f"{year}-12-31"

	holidays = get_holidays(year_start, year_end, employee_filters)
	leaves = get_leaves(year_start, year_end, employee_filters)
	shift_rows = get_shift_rows(year_start, year_end, employee_filters, shift_filters)
	shifts = group_by_employee(shift_rows)
	day_markers = get_year_day_markers(year_start, year_end, holidays)

	return {
		# Holidays and calendar Events are shown as top date-header markers only in
		# the annual Planner. They are intentionally not merged into employee cells.
		"events": merge_employee_events(leaves, shifts),
		"project_rows": get_year_project_rows(shift_rows, year_start, year_end),
		"day_markers": day_markers,
	}


def _clean_filters(filters: dict | str | None) -> dict:
	if not filters:
		return {}
	if isinstance(filters, str):
		filters = frappe.parse_json(filters) or {}
	return {key: value for key, value in dict(filters).items() if value not in (None, "")}


def merge_employee_events(*event_groups: dict[str, list[dict]]) -> dict[str, list[dict]]:
	events = {}
	for event_group in event_groups:
		for key, value in event_group.items():
			if key in events:
				events[key].extend(value)
			else:
				events[key] = value
	return events


def _append_day_marker(markers: dict[str, list[dict]], date, marker: dict) -> None:
	if not date:
		return
	markers.setdefault(str(getdate(date)), []).append(marker)


def _safe_date(value):
	if not value:
		return None
	try:
		return getdate(value)
	except Exception:
		return None


def add_holiday_day_markers(markers: dict[str, list[dict]], holidays: dict[str, list[dict]] | None) -> None:
	"""Add non-weekly-off holidays to the annual header markers.

	Employee holiday lists often contain weekly-off rows for every weekend. The
	header marker is intended for actual holidays and special days, so weekly off
	rows remain visible in employee cells but are not highlighted across the top.
	"""
	seen = set()

	for employee_holidays in (holidays or {}).values():
		for holiday in employee_holidays or []:
			if holiday.get("weekly_off"):
				continue

			holiday_date = holiday.get("holiday_date")
			if not holiday_date:
				continue

			title = holiday.get("description") or "Holiday"
			key = (str(getdate(holiday_date)), holiday.get("holiday") or title)
			if key in seen:
				continue
			seen.add(key)

			_append_day_marker(
				markers,
				holiday_date,
				{
					"type": "holiday",
					"name": holiday.get("holiday"),
					"title": title,
					"description": title,
					"date": str(getdate(holiday_date)),
					"weekly_off": 0,
				},
			)


def _event_field(meta, candidates: list[str]) -> str | None:
	for field in candidates:
		if meta.has_field(field):
			return field
	return None


def get_calendar_events_for_year(year_start: str, year_end: str) -> list[dict]:
	try:
		event_meta = frappe.get_meta("Event")
	except Exception:
		return []

	starts_field = _event_field(event_meta, ["starts_on", "start_date", "from_date"])
	if not starts_field:
		return []

	ends_field = _event_field(event_meta, ["ends_on", "end_date", "to_date"])
	subject_field = _event_field(event_meta, ["subject", "title", "event_name"])
	description_field = _event_field(event_meta, ["description", "notes"])
	event_type_field = _event_field(event_meta, ["event_type", "type"])
	color_field = _event_field(event_meta, ["color"])
	all_day_field = _event_field(event_meta, ["all_day", "all_day_event"])

	fields = ["name", starts_field]
	for field in [ends_field, subject_field, description_field, event_type_field, color_field, all_day_field]:
		if field and field not in fields:
			fields.append(field)

	try:
		rows = frappe.get_all(
			"Event",
			filters={starts_field: ["<=", f"{year_end} 23:59:59"]},
			fields=fields,
			limit_start=0,
			limit_page_length=ANNUAL_ROSTER_RESULT_LIMIT,
			limit=ANNUAL_ROSTER_RESULT_LIMIT,
		)
	except Exception:
		return []

	start_boundary = getdate(year_start)
	end_boundary = getdate(year_end)
	events = []

	for row in rows:
		start_date = _safe_date(row.get(starts_field))
		if not start_date:
			continue

		end_date = _safe_date(row.get(ends_field)) if ends_field else None
		if not end_date:
			end_date = start_date

		if start_date > end_boundary or end_date < start_boundary:
			continue

		title = row.get(subject_field) if subject_field else None
		events.append(
			{
				"name": row.get("name"),
				"title": title or row.get("name"),
				"description": row.get(description_field) if description_field else None,
				"event_type": row.get(event_type_field) if event_type_field else None,
				"color": row.get(color_field) if color_field else None,
				"all_day": row.get(all_day_field) if all_day_field else None,
				"start_date": str(max(start_date, start_boundary)),
				"end_date": str(min(end_date, end_boundary)),
			}
		)

	return events


def add_calendar_event_day_markers(markers: dict[str, list[dict]], year_start: str, year_end: str) -> None:
	for event in get_calendar_events_for_year(year_start, year_end):
		start_date = getdate(event.get("start_date"))
		end_date = getdate(event.get("end_date"))
		current = start_date

		while current <= end_date:
			_append_day_marker(
				markers,
				current,
				{
					"type": "event",
					"name": event.get("name"),
					"title": event.get("title"),
					"description": event.get("description"),
					"event_type": event.get("event_type"),
					"color": event.get("color"),
					"all_day": event.get("all_day"),
					"start_date": event.get("start_date"),
					"end_date": event.get("end_date"),
				},
			)
			current = getdate(add_days(current, 1))


def get_year_day_markers(year_start: str, year_end: str, holidays: dict[str, list[dict]] | None = None) -> dict[str, list[dict]]:
	markers: dict[str, list[dict]] = {}
	add_holiday_day_markers(markers, holidays)
	add_calendar_event_day_markers(markers, year_start, year_end)
	return markers


@frappe.whitelist()
def get_schedule_from_assignment(shift_schedule_assignment: str):
	shift_schedule = frappe.db.get_value(
		"Shift Schedule Assignment", shift_schedule_assignment, "shift_schedule"
	)
	frequency = frappe.db.get_value("Shift Schedule", shift_schedule, "frequency")
	repeat_on_days = frappe.get_all("Assignment Rule Day", filters={"parent": shift_schedule}, pluck="day")
	return {"frequency": frequency, "repeat_on_days": repeat_on_days}


@frappe.whitelist()
def create_shift_schedule_assignment(
	employee: str,
	company: str,
	shift_type: str,
	status: str,
	start_date: str,
	end_date: str | None,
	repeat_on_days: list[str],
	frequency: str,
	shift_location: str | None = None,
	custom_project: str | None = None,
	note: str | None = None,
) -> None:
	shift_schedule = get_or_insert_shift_schedule(shift_type, frequency, repeat_on_days)

	shift_schedule_assignment = frappe.new_doc("Shift Schedule Assignment")
	shift_schedule_assignment.shift_schedule = shift_schedule
	shift_schedule_assignment.employee = employee
	shift_schedule_assignment.company = company
	shift_schedule_assignment.shift_status = status
	shift_schedule_assignment.shift_location = shift_location
	shift_schedule_assignment.enabled = 0 if end_date else 1

	if custom_project:
		_set_doc_field_if_exists(shift_schedule_assignment, "custom_project", custom_project)
		_set_doc_field_if_exists(
			shift_schedule_assignment,
			"custom_project_name",
			_get_project_title(custom_project),
		)

	shift_schedule_assignment.insert()

	if not end_date or date_diff(end_date, start_date) <= 90:
		create_shift_schedule_shifts_with_planner_fields(
			shift_schedule_assignment.name,
			start_date,
			end_date,
			custom_project,
			note,
		)
		return

	frappe.enqueue(
		create_shift_schedule_shifts_with_planner_fields,
		timeout=4500,
		shift_schedule_assignment_name=shift_schedule_assignment.name,
		start_date=start_date,
		end_date=end_date,
		custom_project=custom_project,
		note=note,
	)


def _validate_shift_type_exists(shift_type: str, label: str | None = None) -> None:
	if not shift_type or not frappe.db.exists("Shift Type", shift_type):
		frappe.throw(_("Shift Type {0} does not exist").format(frappe.bold(label or shift_type or "")))


def _as_bool(value, default: bool = False) -> bool:
	if value is None:
		return default
	if isinstance(value, bool):
		return value
	if isinstance(value, (int, float)):
		return bool(value)
	if isinstance(value, str):
		return value.strip().lower() in ("1", "true", "yes", "y", "on")
	return bool(value)


def _as_int(value, label: str, minimum: int = 0) -> int:
	try:
		int_value = int(value or 0)
	except (TypeError, ValueError):
		frappe.throw(_("{0} must be a whole number.").format(label))
	if int_value < minimum:
		frappe.throw(_("{0} must be at least {1}.").format(label, minimum))
	return int_value


def _normalise_roster_segments(roster_segments) -> list[dict]:
	if isinstance(roster_segments, str):
		roster_segments = frappe.parse_json(roster_segments) or []

	if not isinstance(roster_segments, list) or not roster_segments:
		frappe.throw(_("At least one dynamic rolling roster swing is required."))

	normalised = []
	for index, segment in enumerate(roster_segments, start=1):
		if not isinstance(segment, dict):
			frappe.throw(_("Dynamic rolling roster swing {0} is invalid.").format(index))

		days_on_site = _as_int(
			segment.get("days_on_site"),
			_("Swing {0} Days On Site").format(index),
			minimum=1,
		)
		days_off_site = _as_int(
			segment.get("days_off_site"),
			_("Swing {0} Days Off Site").format(index),
			minimum=0,
		)
		normalised.append({"days_on_site": days_on_site, "days_off_site": days_off_site})

	return normalised


def _create_single_rolling_swing(
	employee: str,
	company: str,
	shift_type: str,
	status: str,
	swing_start,
	swing_end,
	shift_location: str | None = None,
	custom_project: str | None = None,
	note: str | None = None,
	include_fly_in_out: bool = True,
	fly_in_shift_type: str = "FI",
	fly_out_shift_type: str = "FO",
	minimum_on_site_days_for_fi_fo: int = 2,
	minimum_message: str | None = None,
	main_shift_type_label: str | None = None,
) -> None:
	if not include_fly_in_out:
		insert_shift(
			employee=employee,
			company=company,
			shift_type=shift_type,
			start_date=_to_date_str(swing_start),
			end_date=_to_date_str(swing_end),
			status=status,
			shift_location=shift_location,
			custom_project=custom_project,
			note=note,
		)
		return

	if date_diff(swing_end, swing_start) + 1 < minimum_on_site_days_for_fi_fo:
		frappe.throw(minimum_message or _("Days on site must be at least 2 when fly in / fly out is enabled."))

	insert_shift(
		employee=employee,
		company=company,
		shift_type=fly_in_shift_type,
		start_date=_to_date_str(swing_start),
		end_date=_to_date_str(swing_start),
		status=status,
		shift_location=shift_location,
		custom_project=custom_project,
		note=note,
	)

	middle_start = getdate(add_days(swing_start, 1))
	middle_end = getdate(add_days(swing_end, -1))
	if middle_start <= middle_end:
		insert_shift(
			employee=employee,
			company=company,
			shift_type=shift_type,
			start_date=_to_date_str(middle_start),
			end_date=_to_date_str(middle_end),
			status=status,
			shift_location=shift_location,
			custom_project=custom_project,
			note=note,
		)

	insert_shift(
		employee=employee,
		company=company,
		shift_type=fly_out_shift_type,
		start_date=_to_date_str(swing_end),
		end_date=_to_date_str(swing_end),
		status=status,
		shift_location=shift_location,
		custom_project=custom_project,
		note=note,
	)


@frappe.whitelist()
def create_rolling_roster_assignment(
	employee: str,
	company: str,
	shift_type: str,
	status: str,
	start_date: str,
	end_date: str,
	days_on_site: int | str,
	days_off_site: int | str,
	shift_location: str | None = None,
	custom_project: str | None = None,
	note: str | None = None,
	include_fly_in_out: bool | int | str = True,
	fly_in_shift_type: str = "FI",
	fly_out_shift_type: str = "FO",
) -> None:
	"""Create a rolling roster pattern across a date range.

	Example: an 8:6 roster creates 8 working days followed by 6 off days.
	When include_fly_in_out is enabled, the first working day is assigned to FI,
	the final working day is assigned to FO, and the days in between use the
	selected shift type. When disabled, all working days use the selected shift type.
	"""
	days_on_site = int(days_on_site or 0)
	days_off_site = int(days_off_site or 0)
	include_fly_in_out = _as_bool(include_fly_in_out, default=True)

	if days_on_site < 1:
		frappe.throw(_("Days on site must be at least 1."))
	if include_fly_in_out and days_on_site < 2:
		frappe.throw(_("Days on site must be at least 2 when fly in / fly out is enabled."))
	if days_off_site < 0:
		frappe.throw(_("Days off site cannot be negative."))
	if not start_date or not end_date:
		frappe.throw(_("Start Date and End Date are required for a Rolling Roster."))

	_validate_shift_type_exists(shift_type, shift_type)
	if include_fly_in_out:
		_validate_shift_type_exists(fly_in_shift_type, fly_in_shift_type)
		_validate_shift_type_exists(fly_out_shift_type, fly_out_shift_type)

	current = getdate(start_date)
	final_date = getdate(end_date)

	if current > final_date:
		frappe.throw(_("End Date cannot be before Start Date."))

	while current <= final_date:
		swing_start = current
		swing_end = getdate(add_days(swing_start, days_on_site - 1))
		if swing_end > final_date:
			swing_end = final_date

		if not include_fly_in_out:
			insert_shift(
				employee=employee,
				company=company,
				shift_type=shift_type,
				start_date=_to_date_str(swing_start),
				end_date=_to_date_str(swing_end),
				status=status,
				shift_location=shift_location,
				custom_project=custom_project,
				note=note,
			)
			current = getdate(add_days(swing_start, days_on_site + days_off_site))
			continue

		# First day of the swing: fly in.
		insert_shift(
			employee=employee,
			company=company,
			shift_type=fly_in_shift_type,
			start_date=_to_date_str(swing_start),
			end_date=_to_date_str(swing_start),
			status=status,
			shift_location=shift_location,
			custom_project=custom_project,
			note=note,
		)

		if date_diff(swing_end, swing_start) >= 1:
			middle_start = getdate(add_days(swing_start, 1))
			middle_end = getdate(add_days(swing_end, -1))

			# Middle of the swing: selected site shift type.
			if middle_start <= middle_end:
				insert_shift(
					employee=employee,
					company=company,
					shift_type=shift_type,
					start_date=_to_date_str(middle_start),
					end_date=_to_date_str(middle_end),
					status=status,
					shift_location=shift_location,
					custom_project=custom_project,
					note=note,
				)

			# Final day of the swing: fly out.
			insert_shift(
				employee=employee,
				company=company,
				shift_type=fly_out_shift_type,
				start_date=_to_date_str(swing_end),
				end_date=_to_date_str(swing_end),
				status=status,
				shift_location=shift_location,
				custom_project=custom_project,
				note=note,
			)

		current = getdate(add_days(swing_start, days_on_site + days_off_site))


@frappe.whitelist()
def create_dynamic_rolling_roster_assignment(
	employee: str,
	company: str,
	shift_type: str,
	status: str,
	start_date: str,
	end_date: str,
	roster_segments: list[dict] | str,
	shift_location: str | None = None,
	custom_project: str | None = None,
	note: str | None = None,
	include_fly_in_out: bool | int | str = True,
	fly_in_shift_type: str = "FI",
	fly_out_shift_type: str = "FO",
) -> None:
	"""Create a dynamic rolling roster pattern across a date range.

	Example: [{8:6}, {4:3}, {7:7}] will create an 8-on/6-off swing,
	then 4-on/3-off, then 7-on/7-off, then repeat that sequence until
	the end date is reached. Each on-site swing uses the selected shift type,
	with optional FI/FO on the first and last days of each swing.
	"""
	segments = _normalise_roster_segments(roster_segments)
	include_fly_in_out = _as_bool(include_fly_in_out, default=True)

	if not start_date or not end_date:
		frappe.throw(_("Start Date and End Date are required for a Dynamic Rolling Roster."))

	_validate_shift_type_exists(shift_type, shift_type)
	if include_fly_in_out:
		_validate_shift_type_exists(fly_in_shift_type, fly_in_shift_type)
		_validate_shift_type_exists(fly_out_shift_type, fly_out_shift_type)
		for index, segment in enumerate(segments, start=1):
			if segment["days_on_site"] < 2:
				frappe.throw(_("Swing {0} Days On Site must be at least 2 when fly in / fly out is enabled.").format(index))

	current = getdate(start_date)
	final_date = getdate(end_date)

	if current > final_date:
		frappe.throw(_("End Date cannot be before Start Date."))

	segment_index = 0
	while current <= final_date:
		segment = segments[segment_index % len(segments)]
		days_on_site = segment["days_on_site"]
		days_off_site = segment["days_off_site"]

		swing_start = current
		swing_end = getdate(add_days(swing_start, days_on_site - 1))
		if swing_end > final_date:
			swing_end = final_date

		_create_single_rolling_swing(
			employee=employee,
			company=company,
			shift_type=shift_type,
			status=status,
			swing_start=swing_start,
			swing_end=swing_end,
			shift_location=shift_location,
			custom_project=custom_project,
			note=note,
			include_fly_in_out=include_fly_in_out,
			fly_in_shift_type=fly_in_shift_type,
			fly_out_shift_type=fly_out_shift_type,
			minimum_message=_("Each dynamic rolling roster swing must have at least 2 days on site when fly in / fly out is enabled."),
		)

		current = getdate(add_days(swing_start, days_on_site + days_off_site))
		segment_index += 1


@frappe.whitelist()
def create_rolling_day_night_roster_assignment(
	employee: str,
	company: str,
	status: str,
	start_date: str,
	end_date: str,
	days_on_site_ds: int | str,
	days_on_site_ns: int | str,
	days_off_site: int | str,
	shift_location: str | None = None,
	custom_project: str | None = None,
	note: str | None = None,
	include_fly_in_out: bool | int | str = True,
	day_shift_type: str = "DS",
	night_shift_type: str = "NS",
	fly_in_shift_type: str = "FI",
	fly_out_shift_type: str = "FO",
) -> None:
	"""Create a rolling day/night roster pattern across a date range.

	Example: a 16:12 roster can be created by setting 8 days on DS,
	8 days on NS and 12 days off site. When include_fly_in_out is enabled,
	the first working day is assigned to FI and the final working day is
	assigned to FO. The remaining working days are assigned to DS or NS
	based on the day/night split.
	"""
	days_on_site_ds = int(days_on_site_ds or 0)
	days_on_site_ns = int(days_on_site_ns or 0)
	days_off_site = int(days_off_site or 0)
	include_fly_in_out = _as_bool(include_fly_in_out, default=True)

	if days_on_site_ds < 1:
		frappe.throw(_("Days on site for DS must be at least 1."))
	if days_on_site_ns < 1:
		frappe.throw(_("Days on site for NS must be at least 1."))
	if days_off_site < 0:
		frappe.throw(_("Days off site cannot be negative."))
	if not start_date or not end_date:
		frappe.throw(_("Start Date and End Date are required for a Rolling Day/Night Roster."))

	total_on_site_days = days_on_site_ds + days_on_site_ns
	if include_fly_in_out and total_on_site_days < 2:
		frappe.throw(_("Total days on site must be at least 2 when fly in / fly out is enabled."))

	_validate_shift_type_exists(day_shift_type, day_shift_type)
	_validate_shift_type_exists(night_shift_type, night_shift_type)
	if include_fly_in_out:
		_validate_shift_type_exists(fly_in_shift_type, fly_in_shift_type)
		_validate_shift_type_exists(fly_out_shift_type, fly_out_shift_type)

	current = getdate(start_date)
	final_date = getdate(end_date)

	if current > final_date:
		frappe.throw(_("End Date cannot be before Start Date."))

	def queue_segment(segments: list[dict], shift_type_name: str, shift_date) -> None:
		shift_date = getdate(shift_date)
		if segments and segments[-1]["shift_type"] == shift_type_name and getdate(add_days(segments[-1]["end_date"], 1)) == shift_date:
			segments[-1]["end_date"] = shift_date
		else:
			segments.append({"shift_type": shift_type_name, "start_date": shift_date, "end_date": shift_date})

	while current <= final_date:
		swing_start = current
		swing_end = getdate(add_days(swing_start, total_on_site_days - 1))
		if swing_end > final_date:
			swing_end = final_date

		segments: list[dict] = []
		offset = 0
		shift_date = swing_start
		while shift_date <= swing_end:
			if include_fly_in_out and offset == 0:
				shift_type_for_day = fly_in_shift_type
			elif include_fly_in_out and shift_date == swing_end:
				shift_type_for_day = fly_out_shift_type
			elif offset < days_on_site_ds:
				shift_type_for_day = day_shift_type
			else:
				shift_type_for_day = night_shift_type

			queue_segment(segments, shift_type_for_day, shift_date)
			offset += 1
			shift_date = getdate(add_days(shift_date, 1))

		for segment in segments:
			insert_shift(
				employee=employee,
				company=company,
				shift_type=segment["shift_type"],
				start_date=_to_date_str(segment["start_date"]),
				end_date=_to_date_str(segment["end_date"]),
				status=status,
				shift_location=shift_location,
				custom_project=custom_project,
				note=note,
			)

		current = getdate(add_days(swing_start, total_on_site_days + days_off_site))


@frappe.whitelist()
def delete_shift_schedule_assignment(shift_schedule_assignment: str) -> None:
	for shift_assignment in frappe.get_all(
		"Shift Assignment", {"shift_schedule_assignment": shift_schedule_assignment}, pluck="name"
	):
		doc = frappe.get_doc("Shift Assignment", shift_assignment)
		if doc.docstatus == 1:
			doc.cancel()
		frappe.delete_doc("Shift Assignment", shift_assignment)
	frappe.delete_doc("Shift Schedule Assignment", shift_schedule_assignment)


def _normalise_bulk_shift_items(shifts) -> list[dict]:
	if isinstance(shifts, str):
		shifts = frappe.parse_json(shifts) or []

	if not isinstance(shifts, list) or not shifts:
		frappe.throw(_("Please select at least one shift to move or swap."))

	items = []
	seen_dates = set()
	for row in shifts:
		if not isinstance(row, dict):
			continue

		employee = row.get("employee")
		date = _to_date_str(row.get("date"))
		shift = row.get("shift") or row.get("shift_assignment") or row.get("name")

		if not employee or not date:
			continue

		# One selected daily cell per employee/date is enough. Multiple shifts in the
		# same cell are intentionally represented by the primary visible shift.
		key = (employee, date)
		if key in seen_dates:
			continue
		seen_dates.add(key)

		items.append({"employee": employee, "date": date, "shift": shift})

	if not items:
		frappe.throw(_("Please select at least one valid shift to move or swap."))

	employees = {row["employee"] for row in items}
	if len(employees) > 1:
		frappe.throw(_("Bulk shift move/swap can only be used for one employee at a time."))

	return sorted(items, key=lambda row: getdate(row["date"]))


def _find_shift_assignment_for_date(employee: str, date: str, preferred_shift: str | None = None):
	date = _to_date_str(date)
	rows = frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": employee,
			"docstatus": 1,
			"start_date": ["<=", date],
		},
		fields=[
			"name",
			"employee",
			"company",
			"shift_type",
			"start_date",
			"end_date",
			"status",
			"shift_location",
			"custom_project",
			"note",
		],
		order_by="start_date desc, creation desc",
		limit_start=0,
		limit_page_length=50,
		limit=50,
	)

	matching = []
	for row in rows:
		if row.get("end_date") and date_diff(row.get("end_date"), date) < 0:
			continue
		matching.append(row)

	if not matching:
		return None

	if preferred_shift:
		for row in matching:
			if row.get("name") == preferred_shift:
				return row

	return matching[0]


def _shift_snapshot(row, date: str) -> dict:
	return {
		"name": row.get("name"),
		"employee": row.get("employee"),
		"company": row.get("company"),
		"shift_type": row.get("shift_type"),
		"date": _to_date_str(date),
		"status": row.get("status"),
		"shift_location": row.get("shift_location"),
		"custom_project": row.get("custom_project"),
		"note": row.get("note"),
	}


def _target_dates_for_bulk_shift_items(items: list[dict], target_date: str) -> list[str]:
	first_source_date = getdate(items[0]["date"])
	target_start = getdate(target_date)

	return [
		_to_date_str(add_days(target_start, date_diff(getdate(row["date"]), first_source_date)))
		for row in items
	]


def _validate_bulk_shift_targets(target_employee: str, target_dates: list[str]) -> None:
	if not target_dates:
		return

	LeaveApplication = frappe.qb.DocType("Leave Application")
	rows = (
		frappe.qb.from_(LeaveApplication)
		.select(LeaveApplication.name, LeaveApplication.leave_type, LeaveApplication.from_date, LeaveApplication.to_date)
		.where(
			(LeaveApplication.docstatus == 1)
			& (LeaveApplication.status == "Approved")
			& (LeaveApplication.employee == target_employee)
			& (LeaveApplication.from_date <= max(target_dates))
			& (LeaveApplication.to_date >= min(target_dates))
		)
	).run(as_dict=True)

	for date in target_dates:
		day = getdate(date)
		for leave in rows:
			if getdate(leave.from_date) <= day <= getdate(leave.to_date):
				frappe.throw(
					_("Cannot move shifts onto approved leave for {0} on {1}.").format(
						target_employee,
						date,
					)
				)


@frappe.whitelist()
def bulk_move_or_swap_shifts(shifts, target_employee: str, target_date: str) -> None:
	"""Move or swap multiple selected daily shift cells.

	The annual planner sends selected daily cells for a single employee. The first
	selected date is aligned to target_date, then the remaining selected cells keep
	the same date offsets. Existing target shifts are swapped back to the original
	source dates. Empty target dates become normal moves.
	"""
	items = _normalise_bulk_shift_items(shifts)
	target_date = _to_date_str(target_date)

	if not target_employee or not target_date:
		frappe.throw(_("Target employee and target date are required."))

	source_employee = items[0]["employee"]
	target_dates = _target_dates_for_bulk_shift_items(items, target_date)
	source_dates = [row["date"] for row in items]

	if source_employee == target_employee and set(source_dates).intersection(target_dates):
		frappe.throw(_("Please drop the selected shifts onto a different date range."))

	_validate_bulk_shift_targets(target_employee, target_dates)

	source_snapshots = []
	for row in items:
		shift_row = _find_shift_assignment_for_date(row["employee"], row["date"], row.get("shift"))
		if not shift_row:
			frappe.throw(_("Could not find the source shift for {0} on {1}.").format(row["employee"], row["date"]))
		source_snapshots.append(_shift_snapshot(shift_row, row["date"]))

	target_snapshots = []
	for date in target_dates:
		target_shift = _find_shift_assignment_for_date(target_employee, date)
		target_snapshots.append(_shift_snapshot(target_shift, date) if target_shift else None)

	target_employee_company = frappe.db.get_value("Employee", target_employee, "company")
	source_employee_company = frappe.db.get_value("Employee", source_employee, "company")
	if not target_employee_company:
		frappe.throw(_("Could not determine company for target employee {0}.").format(target_employee))
	if not source_employee_company:
		frappe.throw(_("Could not determine company for source employee {0}.").format(source_employee))

	savepoint = "before_bulk_shift_move"
	frappe.db.savepoint(savepoint)

	try:
		# Remove selected source daily cells from latest to earliest so splitting a
		# longer assignment cannot invalidate the remaining selected source dates.
		for snapshot in sorted(source_snapshots, key=lambda row: getdate(row["date"]), reverse=True):
			current_shift = _find_shift_assignment_for_date(source_employee, snapshot["date"], snapshot.get("name"))
			if not current_shift:
				frappe.throw(_("Could not remove source shift for {0} on {1}.").format(source_employee, snapshot["date"]))
			break_shift(current_shift.get("name"), snapshot["date"])

		# Remove any target daily cells that will be swapped back. Again, work from
		# latest to earliest to keep splits predictable.
		for snapshot in sorted(
			[row for row in target_snapshots if row],
			key=lambda row: getdate(row["date"]),
			reverse=True,
		):
			current_shift = _find_shift_assignment_for_date(target_employee, snapshot["date"], snapshot.get("name"))
			if not current_shift:
				continue
			break_shift(current_shift.get("name"), snapshot["date"])

		# Insert the selected source shifts into the target date range.
		for source, target_day in zip(source_snapshots, target_dates, strict=False):
			insert_shift(
				employee=target_employee,
				company=target_employee_company,
				shift_type=source.get("shift_type"),
				start_date=target_day,
				end_date=target_day,
				status=source.get("status"),
				shift_location=source.get("shift_location"),
				custom_project=source.get("custom_project"),
				note=source.get("note"),
			)

		# Swap existing target shifts back to the original source dates.
		for source, target in zip(source_snapshots, target_snapshots, strict=False):
			if not target:
				continue
			insert_shift(
				employee=source_employee,
				company=source_employee_company,
				shift_type=target.get("shift_type"),
				start_date=source.get("date"),
				end_date=source.get("date"),
				status=target.get("status"),
				shift_location=target.get("shift_location"),
				custom_project=target.get("custom_project"),
				note=target.get("note"),
			)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise


@frappe.whitelist()
def swap_shift(
	src_shift: str, src_date: str, tgt_employee: str, tgt_date: str, tgt_shift: str | None
) -> None:
	if src_shift == tgt_shift:
		frappe.throw(_("Source and target shifts cannot be the same"))

	if tgt_shift:
		tgt_shift_doc = frappe.get_doc("Shift Assignment", tgt_shift)
		tgt_company = tgt_shift_doc.company
		break_shift(tgt_shift_doc, tgt_date)
	else:
		tgt_company = frappe.db.get_value("Employee", tgt_employee, "company")

	src_shift_doc = frappe.get_doc("Shift Assignment", src_shift)
	break_shift(src_shift_doc, src_date)
	insert_shift(
		tgt_employee,
		tgt_company,
		src_shift_doc.shift_type,
		tgt_date,
		tgt_date,
		src_shift_doc.status,
		src_shift_doc.shift_location,
		src_shift_doc.get("custom_project"),
		src_shift_doc.get("note"),
	)

	if tgt_shift:
		insert_shift(
			src_shift_doc.employee,
			src_shift_doc.company,
			tgt_shift_doc.shift_type,
			src_date,
			src_date,
			tgt_shift_doc.status,
			tgt_shift_doc.shift_location,
			tgt_shift_doc.get("custom_project"),
			tgt_shift_doc.get("note"),
		)


@frappe.whitelist()
def _to_date_str(value):
	if not value:
		return None
	# getdate handles str/date/datetime; str() gives YYYY-MM-DD for date
	return str(getdate(value))


@frappe.whitelist()
def break_shift(assignment: str | ShiftAssignment, date: str) -> None:
	if isinstance(assignment, str):
		assignment = frappe.get_doc("Shift Assignment", assignment)

	if assignment.end_date and date_diff(assignment.end_date, date) < 0:
		frappe.throw(_("Cannot break shift after end date"))
	if date_diff(assignment.start_date, date) > 0:
		frappe.throw(_("Cannot break shift before start date"))

	employee = assignment.employee
	company = assignment.company
	shift_type = assignment.shift_type
	status = assignment.status
	end_date = assignment.end_date
	shift_location = assignment.shift_location
	custom_project = assignment.get("custom_project")
	note = assignment.get("note")

	if date_diff(date, assignment.start_date) == 0:
		assignment.cancel()
		assignment.delete()
	else:
		assignment.end_date = add_days(date, -1)
		assignment.save()

	if not end_date or date_diff(end_date, date) > 0:
		create_planner_shift_assignment(
			employee=employee,
			company=company,
			shift_type=shift_type,
			start_date=_to_date_str(add_days(date, 1)),
			end_date=_to_date_str(end_date),
			status=status,
			shift_location=shift_location,
			custom_project=custom_project,
			note=note,
		)


@frappe.whitelist()
def insert_shift(
	employee: str,
	company: str,
	shift_type: str,
	start_date: str,
	end_date: str | None,
	status: str,
	shift_location: str | None = None,
	custom_project: str | None = None,
	note: str | None = None,
) -> None:
	from frappe.utils import add_days

	# Treat project as part of the identity so only same-project blocks merge
	filters = {
		"doctype": "Shift Assignment",
		"employee": employee,
		"company": company,
		"shift_type": shift_type,
		"status": status,
		"shift_location": shift_location,
	}

	if _doctype_has_field("Shift Assignment", "custom_project"):
		filters["custom_project"] = custom_project
	if _doctype_has_field("Shift Assignment", "note"):
		filters["note"] = note

	prev_shift = frappe.db.exists(dict({"end_date": add_days(start_date, -1)}, **filters))
	next_shift = (
		frappe.db.exists(dict({"start_date": add_days(end_date, 1)}, **filters)) if end_date else None
	)

	if prev_shift:
		if next_shift:
			end_date = frappe.db.get_value("Shift Assignment", next_shift, "end_date")
			frappe.db.set_value("Shift Assignment", next_shift, "docstatus", 2)
			frappe.delete_doc("Shift Assignment", next_shift)

		frappe.db.set_value("Shift Assignment", prev_shift, "end_date", end_date or None)
		# ensure Planner fields stick even if previous block had blank values
		if custom_project or note:
			apply_planner_project_to_shift_assignments([prev_shift], custom_project=custom_project, note=note)

	elif next_shift:
		frappe.db.set_value("Shift Assignment", next_shift, "start_date", start_date)
		if custom_project or note:
			apply_planner_project_to_shift_assignments([next_shift], custom_project=custom_project, note=note)

	else:
		create_planner_shift_assignment(
			employee=employee,
			company=company,
			shift_type=shift_type,
			start_date=start_date,
			end_date=end_date,
			status=status,
			shift_location=shift_location,
			custom_project=custom_project,
			note=note,
		)


def get_holidays(month_start: str, month_end: str, employee_filters: dict[str, str]) -> dict[str, list[dict]]:
	employee_filters = _clean_filters(employee_filters)
	holidays = {}
	holiday_lists = {}

	for employee in frappe.get_list(
		"Employee",
		filters=employee_filters,
		pluck="name",
		limit_start=0,
		limit_page_length=ANNUAL_ROSTER_RESULT_LIMIT,
	):
		if not (holiday_list := get_holiday_list_for_employee(employee, raise_exception=False)):
			continue
		if holiday_list not in holiday_lists:
			holiday_lists[holiday_list] = frappe.get_all(
				"Holiday",
				filters={"parent": holiday_list, "holiday_date": ["between", [month_start, month_end]]},
				fields=["name as holiday", "holiday_date", "description", "weekly_off"],
			)
		holidays[employee] = holiday_lists[holiday_list].copy()

	return holidays


def get_leaves(month_start: str, month_end: str, employee_filters: dict[str, str]) -> dict[str, list[dict]]:
	employee_filters = _clean_filters(employee_filters)
	LeaveApplication = frappe.qb.DocType("Leave Application")
	Employee = frappe.qb.DocType("Employee")

	query = (
		frappe.qb.select(
			LeaveApplication.name.as_("leave"),
			LeaveApplication.employee,
			LeaveApplication.leave_type,
			LeaveApplication.from_date,
			LeaveApplication.to_date,
			LeaveApplication.description.as_("reason"),
			LeaveApplication.status,
			LeaveApplication.total_leave_days,
			LeaveApplication.half_day,
			LeaveApplication.half_day_date,
		)
		.from_(LeaveApplication)
		.left_join(Employee)
		.on(LeaveApplication.employee == Employee.name)
		.where(
			(LeaveApplication.docstatus == 1)
			& (LeaveApplication.status == "Approved")
			& (LeaveApplication.from_date <= month_end)
			& (LeaveApplication.to_date >= month_start)
		)
	)

	for filter in employee_filters:
		query = query.where(Employee[filter] == employee_filters[filter])

	return group_by_employee(query.run(as_dict=True))


def get_shifts(
	month_start: str, month_end: str, employee_filters: dict[str, str], shift_filters: dict[str, str]
) -> dict[str, list[dict]]:
	return group_by_employee(get_shift_rows(month_start, month_end, employee_filters, shift_filters))


def get_shift_rows(
	month_start: str, month_end: str, employee_filters: dict[str, str], shift_filters: dict[str, str]
) -> list[dict]:
	employee_filters = _clean_filters(employee_filters)
	shift_filters = _clean_filters(shift_filters)

	ShiftAssignment = frappe.qb.DocType("Shift Assignment")
	ShiftType = frappe.qb.DocType("Shift Type")
	Employee = frappe.qb.DocType("Employee")
	Project = frappe.qb.DocType("Project")

	query = (
		frappe.qb.select(
			ShiftAssignment.name,
			ShiftAssignment.employee,
			Employee.employee_name.as_("employee_name"),
			ShiftAssignment.shift_type,
			ShiftAssignment.shift_location,
			ShiftAssignment.start_date,
			ShiftAssignment.end_date,
			ShiftAssignment.status,
			ShiftAssignment.shift_schedule_assignment,
			ShiftAssignment.custom_project,
			ShiftAssignment.custom_project_name,
			ShiftAssignment.note,
			ShiftType.start_time,
			ShiftType.end_time,
			ShiftType.color,
			Project.customer_abbreviation.as_("customer_abbreviation"),
		)
		.from_(ShiftAssignment)
		.left_join(ShiftType)
		.on(ShiftAssignment.shift_type == ShiftType.name)
		.left_join(Employee)
		.on(ShiftAssignment.employee == Employee.name)
		.left_join(Project)
		.on(ShiftAssignment.custom_project == Project.name)
		.where(
			(ShiftAssignment.docstatus == 1)
			& (ShiftAssignment.start_date <= month_end)
			& ((ShiftAssignment.end_date >= month_start) | (ShiftAssignment.end_date.isnull()))
		)
	)

	for filter in employee_filters:
		query = query.where(Employee[filter] == employee_filters[filter])

	for filter in shift_filters:
		query = query.where(ShiftAssignment[filter] == shift_filters[filter])

	return query.run(as_dict=True)


def _first_existing_project_field(candidates: list[str]) -> str | None:
	meta = frappe.get_meta("Project")
	for field in candidates:
		if meta.has_field(field):
			return field
	return None


def _truthy_project_value(value) -> bool:
	if value in (None, ""):
		return False
	if isinstance(value, str):
		return value.strip().lower() not in ("0", "no", "false", "missing", "not entered", "none")
	return bool(value)


def _safe_int(value) -> int:
	try:
		return int(value or 0)
	except (TypeError, ValueError):
		return 0


PROJECT_PO_NUMBER_FIELD_CANDIDATES = [
	"custom_po_number",
	"custom_purchase_order_number",
	"custom_purchase_order",
	"purchase_order_number",
	"purchase_order",
	"po_number",
	"po_no",
]

PROJECT_PO_ENTERED_FIELD_CANDIDATES = [
	"custom_po_entered",
	"custom_purchase_order_entered",
]

PROJECT_DS_REQUESTED_FIELD_CANDIDATES = [
	"ds_number",
	"custom_ds_number",
	"custom_ds_requested",
	"custom_day_shift_requested",
	"custom_day_shifts_requested",
	"ds_requested",
	"day_shift_requested",
	"day_shifts_requested",
]

PROJECT_NS_REQUESTED_FIELD_CANDIDATES = [
	"ns_number",
	"custom_ns_number",
	"custom_ns_requested",
	"custom_night_shift_requested",
	"custom_night_shifts_requested",
	"ns_requested",
	"night_shift_requested",
	"night_shifts_requested",
]

PROJECT_START_DATE_FIELD_CANDIDATES = [
	"expected_start_date",
	"custom_expected_start_date",
	"start_date",
	"custom_start_date",
	"planned_start_date",
	"custom_planned_start_date",
]

PROJECT_END_DATE_FIELD_CANDIDATES = [
	"expected_end_date",
	"custom_expected_end_date",
	"end_date",
	"custom_end_date",
	"planned_end_date",
	"custom_planned_end_date",
]


def _project_meta_fieldtype(fieldname: str | None) -> str | None:
	if not fieldname:
		return None
	try:
		field = frappe.get_meta("Project").get_field(fieldname)
	except Exception:
		return None
	return field.fieldtype if field else None


def _project_planner_edit_fields() -> dict[str, str | None]:
	po_number_field = _first_existing_project_field(PROJECT_PO_NUMBER_FIELD_CANDIDATES)
	po_entered_field = _first_existing_project_field(PROJECT_PO_ENTERED_FIELD_CANDIDATES)
	po_field = po_number_field or po_entered_field

	return {
		"po_field": po_field,
		"po_fieldtype": _project_meta_fieldtype(po_field),
		"po_number_field": po_number_field,
		"po_entered_field": po_entered_field,
		"ds_field": _first_existing_project_field(PROJECT_DS_REQUESTED_FIELD_CANDIDATES),
		"ns_field": _first_existing_project_field(PROJECT_NS_REQUESTED_FIELD_CANDIDATES),
		"is_active_field": _first_existing_project_field(["is_active"]),
		"start_date_field": _first_existing_project_field(PROJECT_START_DATE_FIELD_CANDIDATES),
		"end_date_field": _first_existing_project_field(PROJECT_END_DATE_FIELD_CANDIDATES),
	}


def _personnel_list(value) -> list[str]:
	if not value:
		return []
	if isinstance(value, str):
		return [item.strip() for item in value.split(",") if item.strip()]
	try:
		return [str(item).strip() for item in value if str(item).strip()]
	except TypeError:
		return []


def _normalise_project_date_for_update(value):
	if value in (None, ""):
		return None
	return _to_date_str(value)


def _project_date_values_changed(doc, start_field: str | None, end_field: str | None, start_date, end_date) -> bool:
	if not start_field or not end_field:
		return False

	current_start = _normalise_project_date_for_update(doc.get(start_field))
	current_end = _normalise_project_date_for_update(doc.get(end_field))
	incoming_start = _normalise_project_date_for_update(start_date)
	incoming_end = _normalise_project_date_for_update(end_date)

	return current_start != incoming_start or current_end != incoming_end


def _validate_project_date_range(start_date, end_date) -> None:
	if start_date and end_date and getdate(start_date) > getdate(end_date):
		frappe.throw(_("Project Start Date cannot be after Project End Date."))


@frappe.whitelist()
def get_project_planner_details(project: str) -> dict:
	"""Return editable annual-planner details for a Project span dialog."""
	if not project:
		frappe.throw(_("Project is required"))

	doc = frappe.get_doc("Project", project)
	fields = _project_planner_edit_fields()
	po_field = fields.get("po_field")
	po_fieldtype = fields.get("po_fieldtype")
	ds_field = fields.get("ds_field")
	ns_field = fields.get("ns_field")
	is_active_field = fields.get("is_active_field")
	start_date_field = fields.get("start_date_field")
	end_date_field = fields.get("end_date_field")
	task_count = get_project_task_counts([project]).get(project, 0)
	has_tasks = task_count > 0

	po_value = doc.get(po_field) if po_field else None
	is_po_check = po_fieldtype == "Check"

	return {
		"project": doc.name,
		"project_name": doc.project_name,
		"customer": doc.get("customer") if doc.meta.has_field("customer") else None,
		"custom_project_location": doc.get("custom_project_location") if doc.meta.has_field("custom_project_location") else None,
		"status": doc.status,
		"po_field": po_field,
		"po_fieldtype": po_fieldtype,
		"po_number": "" if is_po_check or po_value is None else str(po_value),
		"po_entered": _truthy_project_value(po_value) if po_field else True,
		"ds_field": ds_field,
		"ds_requested": _safe_int(doc.get(ds_field)) if ds_field else 0,
		"ns_field": ns_field,
		"ns_requested": _safe_int(doc.get(ns_field)) if ns_field else 0,
		"is_active_field": is_active_field,
		"is_active": True if not is_active_field else _truthy_project_value(doc.get(is_active_field)),
		"start_date_field": start_date_field,
		"end_date_field": end_date_field,
		"project_start_date": _normalise_project_date_for_update(doc.get(start_date_field)) if start_date_field else None,
		"project_end_date": _normalise_project_date_for_update(doc.get(end_date_field)) if end_date_field else None,
		"task_count": task_count,
		"has_tasks": has_tasks,
		"can_update_po": bool(po_field),
		"can_update_ds": bool(ds_field),
		"can_update_ns": bool(ns_field),
		"can_update_is_active": bool(is_active_field),
		"can_update_project_dates": bool(start_date_field and end_date_field) and not has_tasks,
	}


@frappe.whitelist()
def update_project_planner_details(
	project: str,
	po_number: str | None = None,
	po_entered: bool | int | str | None = None,
	ds_requested: int | str | None = None,
	ns_requested: int | str | None = None,
	is_active: bool | int | str | None = None,
	project_start_date: str | None = None,
	project_end_date: str | None = None,
) -> dict:
	"""Update the Project fields exposed by the annual project span dialog."""
	if not project:
		frappe.throw(_("Project is required"))

	doc = frappe.get_doc("Project", project)
	fields = _project_planner_edit_fields()

	po_field = fields.get("po_field")
	po_fieldtype = fields.get("po_fieldtype")
	if po_field:
		if po_fieldtype == "Check":
			doc.set(po_field, 1 if _as_bool(po_entered, default=False) else 0)
		else:
			doc.set(po_field, (po_number or "").strip())

	ds_field = fields.get("ds_field")
	if ds_field:
		doc.set(ds_field, _safe_int(ds_requested))

	ns_field = fields.get("ns_field")
	if ns_field:
		doc.set(ns_field, _safe_int(ns_requested))

	is_active_field = fields.get("is_active_field")
	if is_active_field:
		is_active_value = _as_bool(is_active, default=True)
		is_active_fieldtype = _project_meta_fieldtype(is_active_field)
		doc.set(is_active_field, 1 if is_active_fieldtype == "Check" and is_active_value else (0 if is_active_fieldtype == "Check" else ("Yes" if is_active_value else "No")))

	start_date_field = fields.get("start_date_field")
	end_date_field = fields.get("end_date_field")
	if start_date_field or end_date_field:
		if not start_date_field or not end_date_field:
			frappe.throw(_("Project date fields are not fully configured on this site."))

		start_date = _normalise_project_date_for_update(project_start_date)
		end_date = _normalise_project_date_for_update(project_end_date)
		_validate_project_date_range(start_date, end_date)

		if _project_date_values_changed(doc, start_date_field, end_date_field, start_date, end_date):
			task_count = get_project_task_counts([project]).get(project, 0)
			if task_count:
				frappe.throw(_("Project dates cannot be changed because this project already has {0} task(s) assigned.").format(task_count))

			doc.set(start_date_field, start_date)
			doc.set(end_date_field, end_date)

	doc.save()
	return get_project_planner_details(project)


@frappe.whitelist()
def update_project_planner_dates(
	project: str,
	project_start_date: str | None = None,
	project_end_date: str | None = None,
) -> dict:
	"""Update only the Project date range used by the annual planner span drag/resize."""
	if not project:
		frappe.throw(_("Project is required"))

	fields = _project_planner_edit_fields()
	start_date_field = fields.get("start_date_field")
	end_date_field = fields.get("end_date_field")

	if not start_date_field or not end_date_field:
		frappe.throw(_("Project date fields are not fully configured on this site."))

	start_date = _normalise_project_date_for_update(project_start_date)
	end_date = _normalise_project_date_for_update(project_end_date)
	_validate_project_date_range(start_date, end_date)

	doc = frappe.get_doc("Project", project)

	if _project_date_values_changed(doc, start_date_field, end_date_field, start_date, end_date):
		task_count = get_project_task_counts([project]).get(project, 0)
		if task_count:
			frappe.throw(_("Project has tasks assigned, so project dates cannot be changed."))

		doc.set(start_date_field, start_date)
		doc.set(end_date_field, end_date)
		doc.save()

	return get_project_planner_details(project)


def get_project_task_counts(project_names: set[str] | list[str] | tuple[str, ...]) -> dict[str, int]:
	project_names = sorted({project for project in project_names if project})
	if not project_names:
		return {}

	try:
		task_meta = frappe.get_meta("Task")
		if not task_meta.has_field("project"):
			return {}
	except Exception:
		return {}

	try:
		rows = frappe.get_all(
			"Task",
			filters={"project": ["in", project_names]},
			fields=["project", "count(name) as task_count"],
			group_by="project",
			limit_start=0,
			limit_page_length=ANNUAL_ROSTER_RESULT_LIMIT,
			limit=ANNUAL_ROSTER_RESULT_LIMIT,
		)
	except Exception:
		return {}

	return {row.project: _safe_int(row.task_count) for row in rows if row.get("project")}


def _project_date_field(candidates: list[str]) -> str | None:
	return _first_existing_project_field(candidates)


def _safe_project_date(value):
	if not value:
		return None
	try:
		return getdate(value)
	except Exception:
		return None


def _project_overlaps_year(project: dict, year_start_date, year_end_date, start_field: str | None, end_field: str | None) -> bool:
	start_date = _safe_project_date(project.get(start_field)) if start_field else None
	end_date = _safe_project_date(project.get(end_field)) if end_field else None

	# If a Project has no date range, do not include it just because it is active.
	# Projects with roster allocations are still included later through the shift fallback.
	if not start_date and not end_date:
		return False

	if not start_date:
		start_date = year_start_date
	if not end_date:
		end_date = year_end_date

	return start_date <= year_end_date and end_date >= year_start_date


def _project_bounds_for_year(project: dict, year_start_date, year_end_date, start_field: str | None, end_field: str | None, fallback_bounds: dict | None = None):
	start_date = _safe_project_date(project.get(start_field)) if start_field else None
	end_date = _safe_project_date(project.get(end_field)) if end_field else None

	if fallback_bounds:
		start_date = start_date or fallback_bounds.get("start")
		end_date = end_date or fallback_bounds.get("end")

	if not start_date and not end_date:
		return None

	if not start_date:
		start_date = year_start_date
	if not end_date:
		end_date = year_end_date

	if start_date > year_end_date or end_date < year_start_date:
		return None

	return max(start_date, year_start_date), min(end_date, year_end_date)


def get_active_project_meta(
	project_names: list[str] | set[str] | None = None,
	year_start: str | None = None,
	year_end: str | None = None,
) -> dict[str, dict]:
	"""Return Project metadata for projects that should appear in annual planning rows.

	When a year range is supplied, this intentionally looks up active Projects by
	Project date range as well as projects referenced by Shift Assignment rows. This
	means the annual Projects table can show every active project in that year, not
	only the projects that already have people allocated to shifts.

	ANNUAL_ROSTER_RESULT_LIMIT is deliberately explicit because some Frappe list
	queries otherwise fall back to the default page length of about 20 rows.
	"""
	project_names = sorted({project for project in (project_names or []) if project})
	year_start_date = getdate(year_start) if year_start else None
	year_end_date = getdate(year_end) if year_end else None

	inactive_statuses = [
		"Completed",
		"Cancelled",
		"Closed",
		"Archived",
		"Inactive",
	]

	po_field = _first_existing_project_field([
		"custom_po_entered",
		"custom_purchase_order_entered",
		"custom_purchase_order",
		"custom_purchase_order_number",
		"purchase_order",
		"purchase_order_number",
		"po_number",
		"po_no",
	])
	ds_field = _first_existing_project_field([
		"ds_number",
		"custom_ds_number",
		"custom_ds_requested",
		"custom_day_shift_requested",
		"custom_day_shifts_requested",
		"ds_requested",
		"day_shift_requested",
		"day_shifts_requested",
	])
	ns_field = _first_existing_project_field([
		"ns_number",
		"custom_ns_number",
		"custom_ns_requested",
		"custom_night_shift_requested",
		"custom_night_shifts_requested",
		"ns_requested",
		"night_shift_requested",
		"night_shifts_requested",
	])

	customer_abbreviation_field = _first_existing_project_field(["customer_abbreviation"])
	customer_field = _first_existing_project_field(["customer"])
	project_location_field = _first_existing_project_field(["custom_project_location"])
	project_notes_field = _first_existing_project_field(["notes"])
	roster_or_shutdown_field = _first_existing_project_field(["roster_or_shutdown"])
	shifts_filled_field = _first_existing_project_field(["shifts_filled"])
	is_active_field = _first_existing_project_field(["is_active"])
	start_field = _project_date_field(PROJECT_START_DATE_FIELD_CANDIDATES)
	end_field = _project_date_field(PROJECT_END_DATE_FIELD_CANDIDATES)

	optional_fields = [
		field
		for field in [
			po_field,
			ds_field,
			ns_field,
			customer_abbreviation_field,
			customer_field,
			project_location_field,
			project_notes_field,
			roster_or_shutdown_field,
			shifts_filled_field,
			is_active_field,
			start_field,
			end_field,
		]
		if field
	]

	base_filters = {
		"status": ["not in", inactive_statuses],
	}

	project_filters = dict(base_filters)
	if project_names and not (year_start_date and year_end_date):
		project_filters["name"] = ["in", project_names]

	projects = frappe.get_all(
		"Project",
		filters=project_filters,
		fields=["name", "project_name", "status", *optional_fields],
		limit_start=0,
		limit_page_length=ANNUAL_ROSTER_RESULT_LIMIT,
		limit=ANNUAL_ROSTER_RESULT_LIMIT,
	)

	# If a year was supplied, include Projects that overlap the year by their Project
	# date range. Also keep any referenced projects from Shift Assignment as a safety
	# fallback even when their Project date fields are blank.
	if year_start_date and year_end_date:
		referenced_names = set(project_names)
		projects = [
			project
			for project in projects
			if _project_overlaps_year(project, year_start_date, year_end_date, start_field, end_field)
			or project.get("name") in referenced_names
		]

	customer_details = {}
	if customer_field:
		customer_fields = ["name"]
		customer_color_field = None
		customer_name_field = None
		try:
			customer_meta = frappe.get_meta("Customer")
			if customer_meta.has_field("customer_color"):
				customer_color_field = "customer_color"
			if customer_meta.has_field("customer_name"):
				customer_name_field = "customer_name"
		except Exception:
			customer_color_field = None
			customer_name_field = None

		if customer_color_field:
			customer_fields.append(customer_color_field)
		if customer_name_field:
			customer_fields.append(customer_name_field)

		customer_names = sorted(
			{project.get(customer_field) for project in projects if project.get(customer_field)}
		)
		if customer_names:
			customer_details = {
				customer.name: customer
				for customer in frappe.get_all(
					"Customer",
					filters={"name": ["in", customer_names]},
					fields=customer_fields,
					limit_start=0,
					limit_page_length=ANNUAL_ROSTER_RESULT_LIMIT,
					limit=ANNUAL_ROSTER_RESULT_LIMIT,
				)
			}

	for project in projects:
		customer = project.get(customer_field) if customer_field else None
		customer_detail = customer_details.get(customer) if customer else None

		# If no PO field exists on this site yet, default to entered so the annual
		# bar uses the same visual style as the current monthly project timeline.
		project["po_entered"] = True if not po_field else _truthy_project_value(project.get(po_field))
		project["ds_requested"] = _safe_int(project.get(ds_field)) if ds_field else 0
		project["ns_requested"] = _safe_int(project.get(ns_field)) if ns_field else 0
		project["customer"] = customer
		project["customer_name"] = (
			customer_detail.get("customer_name") if customer_detail and customer_detail.get("customer_name") else customer
		)
		project["customer_color"] = (
			customer_detail.get("customer_color") if customer_detail else None
		)
		project["custom_project_location"] = project.get(project_location_field) if project_location_field else None
		project["notes"] = project.get(project_notes_field) if project_notes_field else None
		project["roster_or_shutdown"] = (
			project.get(roster_or_shutdown_field) if roster_or_shutdown_field else None
		)
		project["shifts_filled"] = (
			_truthy_project_value(project.get(shifts_filled_field)) if shifts_filled_field else None
		)
		# Project.is_active is used by the annual view to show projects that are still
		# waiting on confirmation with a lighter project span colour. If the field is
		# not present on a site, treat projects as active so existing behaviour remains unchanged.
		project["is_active"] = True if not is_active_field else _truthy_project_value(project.get(is_active_field))
		project["_start_field"] = start_field
		project["_end_field"] = end_field

	return {project.name: project for project in projects}


def get_shift_project_bounds(shift_rows: list[dict], year_start_date, year_end_date) -> dict[str, dict]:
	bounds: dict[str, dict] = {}
	for shift in shift_rows:
		project = shift.get("custom_project")
		if not project:
			continue

		start_date = max(getdate(shift.get("start_date")), year_start_date)
		end_date = getdate(shift.get("end_date")) if shift.get("end_date") else year_end_date
		end_date = min(end_date, year_end_date)

		if start_date > year_end_date or end_date < year_start_date:
			continue

		current = bounds.setdefault(project, {"start": start_date, "end": end_date})
		if start_date < current["start"]:
			current["start"] = start_date
		if end_date > current["end"]:
			current["end"] = end_date

	return bounds


def _shift_employee_label(shift: dict) -> str:
	employee_name = (shift.get("employee_name") or "").strip()
	employee = (shift.get("employee") or "").strip()
	return employee_name or employee


def _shift_type_key(shift_type: str | None) -> str:
	return (shift_type or "").strip().upper()


def _shift_type_suffix_key(shift_type: str | None) -> str:
	"""Return the roster meaning part of a Shift Type name.

	Examples:
	- DS -> DS
	- NS -> NS
	- FG-DS -> DS
	- RH-NS -> NS
	- FG-DS-CREW-1 -> DS-CREW-1
	"""
	key = _shift_type_key(shift_type)
	for prefix in ("FG-", "RH-"):
		if key.startswith(prefix):
			return key[len(prefix):]
	return key


def _is_ds_personnel_shift(shift_type: str | None) -> bool:
	suffix = _shift_type_suffix_key(shift_type)
	return suffix == "DS" or suffix.startswith("DS-")


def _is_ns_personnel_shift(shift_type: str | None) -> bool:
	suffix = _shift_type_suffix_key(shift_type)
	return suffix == "NS" or suffix.startswith("NS-")


def get_year_project_rows(shift_rows: list[dict], year_start: str, year_end: str) -> list[dict]:
	projects = {}
	shift_summaries: dict[str, dict] = {}
	year_start_date = getdate(year_start)
	year_end_date = getdate(year_end)
	shift_project_bounds = get_shift_project_bounds(shift_rows, year_start_date, year_end_date)

	active_projects = get_active_project_meta(
		{shift.get("custom_project") for shift in shift_rows if shift.get("custom_project")},
		year_start,
		year_end,
	)
	task_counts = get_project_task_counts(active_projects.keys())

	# First summarise roster allocations by project/day. This lets the project hover
	# and future project span details still know about employees/shift types when
	# shifts exist, without requiring shifts to exist before the project is shown.
	for shift in shift_rows:
		project = shift.get("custom_project")
		if not project or project not in active_projects:
			continue

		start_date = max(getdate(shift.get("start_date")), year_start_date)
		end_date = getdate(shift.get("end_date")) if shift.get("end_date") else year_end_date
		end_date = min(end_date, year_end_date)

		current = start_date
		while current <= end_date:
			date_key = str(current)
			cell = shift_summaries.setdefault(project, {}).setdefault(
				date_key,
				{
					"count": 0,
					"color": None,
					"_shift_types": [],
					"_employees": [],
					"_ds_personnel": [],
					"_ns_personnel": [],
				},
			)
			cell["count"] += 1
			if not cell["color"] and shift.get("color"):
				cell["color"] = str(shift.get("color")).lower()
			if shift.get("shift_type"):
				cell["_shift_types"].append(shift.get("shift_type"))
			if shift.get("employee"):
				cell["_employees"].append(shift.get("employee"))

			employee_label = _shift_employee_label(shift)
			shift_type = shift.get("shift_type")
			if employee_label and _is_ds_personnel_shift(shift_type):
				cell["_ds_personnel"].append(employee_label)
			elif employee_label and _is_ns_personnel_shift(shift_type):
				cell["_ns_personnel"].append(employee_label)

			current = getdate(add_days(current, 1))

	for project, project_meta in active_projects.items():
		project_name = project_meta.get("project_name") or project
		bounds = _project_bounds_for_year(
			project_meta,
			year_start_date,
			year_end_date,
			project_meta.get("_start_field"),
			project_meta.get("_end_field"),
			shift_project_bounds.get(project),
		)
		if not bounds:
			continue

		project_task_count = task_counts.get(project, 0)

		projects[project] = {
			"project": project,
			"project_name": project_name,
			"status": project_meta.get("status"),
			"customer": project_meta.get("customer"),
			"customer_name": project_meta.get("customer_name"),
			"custom_project_location": project_meta.get("custom_project_location"),
			"notes": project_meta.get("notes"),
			"roster_or_shutdown": project_meta.get("roster_or_shutdown"),
			"task_count": project_task_count,
			"has_tasks": project_task_count > 0,
			"shifts_filled": project_meta.get("shifts_filled"),
			"is_active": project_meta.get("is_active"),
			"po_entered": project_meta.get("po_entered"),
			"ds_requested": _safe_int(project_meta.get("ds_requested")),
			"ns_requested": _safe_int(project_meta.get("ns_requested")),
			"customer_color": project_meta.get("customer_color"),
			"assignments": {},
		}

		current = bounds[0]
		while current <= bounds[1]:
			date_key = str(current)
			cell = projects[project]["assignments"].setdefault(
				date_key,
				{
					"count": 0,
					"color": None,
					"_shift_types": [],
					"_employees": [],
					"_ds_personnel": [],
					"_ns_personnel": [],
				},
			)

			shift_cell = shift_summaries.get(project, {}).get(date_key)
			if shift_cell:
				cell["count"] += shift_cell.get("count", 0)
				cell["color"] = shift_cell.get("color") or cell.get("color")
				cell["_shift_types"].extend(shift_cell.get("_shift_types", []))
				cell["_employees"].extend(shift_cell.get("_employees", []))
				cell["_ds_personnel"].extend(shift_cell.get("_ds_personnel", []))
				cell["_ns_personnel"].extend(shift_cell.get("_ns_personnel", []))

			current = getdate(add_days(current, 1))

	for project in projects.values():
		project_ds_personnel = set()
		project_ns_personnel = set()

		for cell in project["assignments"].values():
			shift_types = sorted(set(cell.pop("_shift_types", [])))
			employees = sorted(set(cell.pop("_employees", [])))
			ds_personnel = sorted(set(cell.pop("_ds_personnel", [])))
			ns_personnel = sorted(set(cell.pop("_ns_personnel", [])))
			project_ds_personnel.update(ds_personnel)
			project_ns_personnel.update(ns_personnel)
			cell["shift_types"] = shift_types
			cell["employees"] = employees
			cell["ds_personnel"] = ds_personnel
			cell["ns_personnel"] = ns_personnel
			cell["count"] = len(employees) or cell["count"]
			if cell["count"] > 1:
				cell["label"] = str(cell["count"])
			else:
				cell["label"] = shift_types[0] if shift_types else ""

		project["ds_personnel"] = sorted(project_ds_personnel)
		project["ns_personnel"] = sorted(project_ns_personnel)

	return sorted(
		projects.values(),
		key=lambda row: (
			(row.get("customer_name") or row.get("customer") or ""),
			(row.get("custom_project_location") or ""),
			row.get("project_name") or "",
		),
	)

def group_by_employee(events: list[dict]) -> dict[str, list[dict]]:
	grouped_events = {}
	for event in events:
		grouped_events.setdefault(event["employee"], []).append(
			{k: v for k, v in event.items() if k != "employee"}
		)
	return grouped_events


@frappe.whitelist()
def get_available_employees(from_date: str, to_date: str, **employee_filters) -> dict:
	ALLOWED = {"company", "department", "branch", "designation", "status"}
	ef = {k: v for k, v in (employee_filters or {}).items() if k in ALLOWED and v}
	all_emp_names = set(
		frappe.get_all(
			"Employee",
			filters=ef,
			pluck="name",
			limit_start=0,
			limit_page_length=ANNUAL_ROSTER_RESULT_LIMIT,
			limit=ANNUAL_ROSTER_RESULT_LIMIT,
		)
	)
	if not all_emp_names:
		return {"employees": []}
	ShiftAssignment = frappe.qb.DocType("Shift Assignment")
	busy_rows = (
		frappe.qb.select(ShiftAssignment.employee)
		.from_(ShiftAssignment)
		.where(
			(ShiftAssignment.docstatus == 1)
			& (ShiftAssignment.start_date <= to_date)
			& ((ShiftAssignment.end_date >= from_date) | (ShiftAssignment.end_date.isnull()))
			& (ShiftAssignment.employee.isin(list(all_emp_names)))
		)
		.distinct()
	).run(pluck="employee")

	busy = set(busy_rows or [])
	available = sorted(all_emp_names - busy)
	return {"employees": [{"name": e} for e in available]}
