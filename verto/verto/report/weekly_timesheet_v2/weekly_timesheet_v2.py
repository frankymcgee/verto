# Copyright (c) 2024, Webwire and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = []
    data = []

    # Fetch data grouped by employee
    timesheets = frappe.db.sql("""
        SELECT
            u.full_name AS employee_name,
            dt.date AS date_submitted,
            DAYNAME(dt.date) AS day_of_week,
            dt.project AS project_name,
            dt.shift AS shift_type,
            dt.start_time AS start_time,
            dt.end_time AS end_time,
            dt.duration / 3600 AS hours_worked
        FROM
            `tabDaily Timesheet` dt
        JOIN
            `tabUser` u ON dt.owner = u.name
        WHERE
            dt.date BETWEEN %(start_date)s AND %(end_date)s
            AND (%(exclude_operations)s = 'No' 
                OR dt.project NOT LIKE '%%Operations & Execution%%')
        ORDER BY
            u.full_name, dt.date
    """, filters, as_dict=1)

    # Generate HTML content
    html = """
    <style>
        .employee-group { page-break-after: always; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #000; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
    """

    current_employee = None
    for timesheet in timesheets:
        if timesheet['employee_name'] != current_employee:
            if current_employee is not None:
                html += "</tbody></table></div>"
            current_employee = timesheet['employee_name']
            html += f"""
            <div class="employee-group">
                <h2>{timesheet['employee_name']}</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Date Submitted</th>
                            <th>Day of Week</th>
                            <th>Project Name</th>
                            <th>Shift Type</th>
                            <th>Start Time</th>
                            <th>End Time</th>
                            <th>Hours Worked</th>
                        </tr>
                    </thead>
                    <tbody>
            """
        html += f"""
        <tr>
            <td>{timesheet['date_submitted']}</td>
            <td>{timesheet['day_of_week']}</td>
            <td>{timesheet['project_name']}</td>
            <td>{timesheet['shift_type']}</td>
            <td>{timesheet['start_time']}</td>
            <td>{timesheet['end_time']}</td>
            <td>{timesheet['hours_worked']}</td>
        </tr>
        """
    if current_employee is not None:
        html += "</tbody></table></div>"

    # Return the HTML content as a data column
    return [{
        'fieldname': 'html',
        'fieldtype': 'HTML',
        'label': 'Report',
        'options': html
    }], []
