import Gantt from "frappe-gantt";
import "./gantt_view";

// Keep the constructor with this view, independent of window.Gantt or lazy assets.
frappe.views.GanttView.Gantt = Gantt;
