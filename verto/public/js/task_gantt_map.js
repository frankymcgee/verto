frappe.provide("frappe.views.calendar");
frappe.views.calendar["Task"] = Object.assign({}, frappe.views.calendar["Task"], {
  gantt: Object.assign({}, (frappe.views.calendar["Task"] || {}).gantt, {
    field_map: Object.assign(
      {
        id: "name",
        title: "subject",
        start: "exp_start_date",
        end: "exp_end_date",
        exp_start_time: "exp_start_time",
        exp_end_time: "exp_end_time",
        progress: "progress"
      },
      ((frappe.views.calendar["Task"] || {}).gantt || {}).field_map || {}
    )
  })
});