# verto/overrides/shift_schedule_assignment.py
import frappe
from frappe.model.document import Document
from frappe.utils import add_days, get_weekday, getdate, nowdate, format_date, get_link_to_form
from frappe import _

from verto.api.shift_create import create_shift_assignment


class CustomShiftScheduleAssignment(Document):
    def validate(self):
        self.validate_existing_shift_assignments()

    def validate_existing_shift_assignments(self):
        if self.has_value_changed("create_shifts_after") and not self.is_new():
            existing, last_end = self.get_existing_shift_assignments()
            if existing:
                frappe.throw(
                    msg=_(
                        "Shift assignments for {0} after {1} are already created. "
                        "Please change {2} date to a date later than {3} {4}"
                    ).format(
                        frappe.bold(self.shift_schedule),
                        frappe.bold(self.create_shifts_after),
                        frappe.bold("Create Shifts After"),
                        frappe.bold(last_end),
                        (
                            "<br><br><ul><li>"
                            + "</li><li>".join(
                                get_link_to_form("Shift Assignment", s) for s in existing
                            )
                            + "</li></ul>"
                        ),
                    ),
                    title=_("Existing Shift Assignments"),
                )

    def get_existing_shift_assignments(self):
        ssa = frappe.qb.DocType("Shift Schedule Assignment")
        sa = frappe.qb.DocType("Shift Assignment")

        q = (
            frappe.qb.from_(sa)
            .inner_join(ssa).on(sa.shift_schedule_assignment == ssa.name)
            .select(sa.name, sa.end_date)
            .where((sa.end_date >= self.create_shifts_after)
                   & (sa.status == "Active")
                   & (sa.employee == self.employee))
            .orderby(sa.end_date)
        )
        rows = q.run(as_dict=True)
        return [r.name for r in rows], (rows[-1].end_date if rows else None)

    def create_shifts(self, start_date: str, end_date: str | None = None) -> None:
        shift_schedule = frappe.get_doc("Shift Schedule", self.shift_schedule)
        gap = {"Every Week": 0, "Every 2 Weeks": 1, "Every 3 Weeks": 2, "Every 4 Weeks": 3}[shift_schedule.frequency]

        date = start_date
        block_start = None
        week_end_day = get_weekday(getdate(add_days(start_date, -1)))
        repeat_on_days = [d.day for d in shift_schedule.repeat_on_days]

        if not end_date:
            end_date = add_days(start_date, 90)

        while date <= end_date:
            weekday = get_weekday(getdate(date))
            if weekday in repeat_on_days:
                if not block_start:
                    block_start = date
                if date == end_date:
                    self.create_individual_assignment(shift_schedule.shift_type, block_start, date)
            elif block_start:
                self.create_individual_assignment(shift_schedule.shift_type, block_start, add_days(date, -1))
                block_start = None

            if weekday == week_end_day and gap:
                if block_start:
                    self.create_individual_assignment(shift_schedule.shift_type, block_start, date)
                    block_start = None
                date = add_days(date, 7 * gap)

            date = add_days(date, 1)

    def _resolve_project_id(self, value: str | None) -> str | None:
        if not value:
            return None
        if frappe.db.exists("Project", value):
            return value
        resolved = frappe.db.get_value("Project", {"subject": value}, "name")
        if resolved:
            return resolved
        frappe.throw(f"Project '{value}' was not found as Project ID or subject.")

    def create_individual_assignment(self, shift_type: str, start_date: str, end_date: str) -> None:
        project_id = self._resolve_project_id(getattr(self, "custom_project", None))
        create_shift_assignment(
            employee=self.employee,
            company=self.company,
            shift_type=shift_type,
            start_date=start_date,
            end_date=end_date,
            status=self.shift_status,
            custom_project=project_id,
            shift_location=self.shift_location,
            shift_schedule_assignment=self.name,
        )
        # keep rolling window without bumping modified
        self.db_set("create_shifts_after", end_date, update_modified=False)


def process_auto_shift_creation():
    ssa_names = frappe.get_all(
        "Shift Schedule Assignment",
        filters={"enabled": 1, "create_shifts_after": ["<=", nowdate()]},
        pluck="name",
    )
    for name in ssa_names:
        try:
            doc = frappe.get_doc("Shift Schedule Assignment", name)
            start_date = doc.create_shifts_after
            doc.create_shifts(add_days(doc.create_shifts_after, 1))
            doc.add_comment(
                comment_type="Info",
                text=_("Shift Assignments created for the schedule between {0} and {1} via background job")
                .format(frappe.bold(format_date(start_date)), frappe.bold(format_date(doc.create_shifts_after))),
            )
        except Exception as e:
            frappe.log_error(e)
            continue
