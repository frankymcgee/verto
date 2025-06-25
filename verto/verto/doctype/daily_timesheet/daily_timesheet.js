// Copyright (c) 2024, Webwire and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Daily Timesheet", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Daily Timesheet', {
    start_time: function(frm) {
        calculate_duration(frm);
    },
    end_time: function(frm) {
        calculate_duration(frm);
    },
    refresh: function(frm) {
        // Get the current logged-in user
        let currentUser = frappe.session.user;

        // Fetch the full name of the current user
        frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: 'User',
                filters: { 'name': currentUser },
                fieldname: ['full_name']
            },
            callback: function(r) {
                if (r.message) {
                    let fullName = r.message.full_name;
                    // Set the current_user field with the full name
                    frm.set_value('current_user', fullName);

                    // Fetch the first shift allocation based on the filters
                    frappe.call({
                        method: 'frappe.client.get_list',
                        args: {
                            doctype: 'Shift Assignment',
                            filters: [
                                ["start_date", "<=", frm.doc.date],
                                ["end_date", ">=", frm.doc.date],
                                ["employee_name", "=", fullName],
                                ["docstatus", "=", "1"]
                            ],
                            limit: 1,
                            fields: ['name']  // Assuming 'name' is the field you want for shift_allocation
                        },
                        callback: function(r) {
                            if (r.message && r.message.length > 0) {
                                let firstResult = r.message[0].name;
                                frm.set_value('shift_allocation', firstResult);
                            } else {
                                // Show an error message if no shift allocation is found
                                frappe.msgprint(__('You have no allocated shifts available to fill out a timesheet. Please contact the office for a shift allocation.'));
                            }
                        }
                    });
                }
            }
        });

        // Set the date field to today's date if it is not already set
        if (!frm.doc.date_field) {
            let today = frappe.datetime.get_today();
            frm.set_value('date', today);
        }
        
        // Function to add a button
        const add_button = function (location, class_name, label, style, callback, prepend = false) {
            if (!$(location).find(`.${class_name}`).length) {
                const button_html = `
                    <button class="btn btn-primary btn-xs ${class_name}" style="${style}">
                        ${label}
                    </button>
                `;
                if (prepend) {
                    $(location).prepend(button_html);
                } else {
                    $(location).append(button_html);
                }
                $(`.${class_name}`).on('click', callback);
            }
        };

        if (!frm.is_new()) {
            add_button(
                frm.page.page_actions,
                'custom-new-record-btn',
                '+',
                'display: flex; width: auto; align-items: center; justify-content: center;',
                function () {
                    frappe.new_doc(frm.doc.doctype);
                },
                true
            );
        }

        let custom_container = frm.$wrapper.find('.form-page').next('.custom-action-container');
        if (!custom_container.length) {
            custom_container = $(
                '<div class="custom-action-container" style="width: 100%; margin-top: 20px; margin-bottom: 20px;"></div>'
            ).insertAfter(frm.$wrapper.find('.form-page'));
        }

        add_button(
            custom_container,
            'custom-save-bottom-btn',
            'Save',
            'width: 100%; padding: 12px 0; font-size: 16px; text-align: center; display: block;',
            function () {
                frm.save_or_update();
            }
        );
    },
    after_save: function(frm) {
        let week_start = getMonday(frm.doc.date);
        let week_end = frappe.datetime.add_days(week_start, 6);

        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Timesheet",
                filters: {
                    employee_name: frm.doc.user_full_name,
                    parent_project: frm.doc.project_id,  // ✅ Ensuring we only check for the same project
                    start_date: ["between", [week_start, week_end]]
                },
                fields: ["name"]
            },
            callback: function(response) {
                let existing_timesheet = response.message.length ? response.message[0].name : null;
                create_or_update_timesheet(frm, existing_timesheet, week_start);
            }
        });
    }
});

function calculate_duration(frm) {
    if (frm.doc.start_time && frm.doc.end_time) {
        // Parse start and end times as moment.js objects
        var start_time = moment(frm.doc.start_time, 'HH:mm:ss');
        var end_time = moment(frm.doc.end_time, 'HH:mm:ss');

        // Handle case where end time is past midnight
        if (end_time.isBefore(start_time)) {
            end_time.add(1, 'day');
        }

        // Calculate the difference in milliseconds
        var duration_ms = end_time.diff(start_time);

        // Convert duration from milliseconds to seconds
        var duration_seconds = duration_ms / 1000;

        // Set the duration in the form
        frm.set_value('duration', duration_seconds);
    }
}

function create_or_update_timesheet(frm, timesheet_id, week_start) {
    let total_hours = parseFloat(frm.doc.duration);
    let hours_in_float = total_hours / 3600;

    let formatted_from_time = moment(format_datetime(frm.doc.date, frm.doc.start_time)).format("YYYY-MM-DD HH:mm:ss");

    let formatted_to_time = moment(formatted_from_time, "YYYY-MM-DD HH:mm:ss")
        .add(hours_in_float, 'hours')
        .format("YYYY-MM-DD HH:mm:ss");

    console.log("total_hours (raw):", frm.doc.total_hours);
    console.log("total_hours (parsed):", total_hours);
    console.log("hours_in_float:", hours_in_float);
    console.log("formatted_from_time:", formatted_from_time);
    console.log("formatted_to_time (after adding):", formatted_to_time);

    let work_day_name = get_day_name(frm.doc.date);

    let timesheet_entry = {
        activity_type: "Execution",
        from_time: formatted_from_time,
        to_time: formatted_to_time,
        hours: hours_in_float,
        is_billable: 1,
        project: frm.doc.project_id,
        shift_type: frm.doc.shift,
        work_day: work_day_name,
        description: frm.doc.comments
    };

    if (timesheet_id) {
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Timesheet",
                name: timesheet_id
            },
            callback: function(response) {
                let timesheet = response.message;

                if (!timesheet.time_logs) {
                    timesheet.time_logs = [];
                }

                timesheet.time_logs.push(timesheet_entry);

                frappe.call({
                    method: "frappe.client.save",
                    args: {
                        doc: timesheet
                    },
                    callback: function() {
                        frappe.msgprint("Updated existing weekly Timesheet for this project.");
                    }
                });
            }
        });
    } else {
        frappe.call({
            method: "frappe.client.insert",
            args: {
                doc: {
                    doctype: "Timesheet",
                    employee_name: frm.doc.user_full_name,
                    start_date: week_start,
                    custom_monday_date: getMonday(frm.doc.date),
                    custom_sunday_date: frappe.datetime.add_days(week_start, 6),
                    customer: frm.doc.customer,
                    parent_project: frm.doc.project_id,
                    time_logs: [timesheet_entry]
                }
            },
            callback: function() {
                frappe.msgprint("Created new weekly Timesheet for this project.");
            }
        });
    }
    setTimeout(() => {window.location.href = '/app/shifts';}, 2000);  // Redirect after 2 seconds
}

// Function to get the Monday of the week for a given date
function getMonday(date) {
    let d = new Date(date);
    let day = d.getDay();
    let diff = day === 0 ? -6 : 1 - day;
    d.setDate(d.getDate() + diff);
    return frappe.datetime.obj_to_str(d);
}

// Function to format datetime correctly (From Time)
function format_datetime(date, time) {
    let time_parts = time.split(":");
    let hours = time_parts[0].padStart(2, '0');
    let minutes = time_parts[1] ? time_parts[1].padStart(2, '0') : "00";
    let seconds = "00";
    return `${date} ${hours}:${minutes}:${seconds}`;
}

// Function to get the day name from a date
function get_day_name(date) {
    let days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
    let d = new Date(date);
    return days[d.getDay()];
}