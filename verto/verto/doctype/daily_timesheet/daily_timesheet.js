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
        if (!frm.doc.current_user) {
            let currentUser = frappe.session.user;

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
                        frm.set_value('current_user', fullName);

                        // Now that we have fullName, do the shift allocation
                        set_shift_allocation(frm, fullName);
                    }
                }
            });
        } else {
            // already has current_user → reuse it
            set_shift_allocation(frm, frm.doc.current_user);
        }        
        // Set the date field to today's date if it is not already set
        if (!frm.doc.date) {
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
    before_save: function(frm) {
        // Skip confirm if we already asked
        if (frm.skip_confirm) {
            frm.skip_confirm = false; // reset for next time
            return;
        }

        if (frm.doc.duration) {
            const hours = (frm.doc.duration / 3600).toFixed(2);

            frappe.validated = false; // stop save

            frappe.confirm(
                __("Your current hours for this shift is {0} hours. Is this correct?", [hours]),
                function() {
                    // ✅ Yes → set guard + retry save
                    frm.skip_confirm = true;
                    frappe.validated = true;
                    frm.save();
                },
                function() {
                    // ❌ No → let them adjust
                    frappe.validated = false;
                }
            );
        }
    },
    after_save: function(frm) {        
        setTimeout(() => {window.location.href = '/app/shifts';}, 2000);  // Redirect after 2 seconds
    }
});

function calculate_duration(frm) {
     if (frm.doc.start_time && frm.doc.end_time) { // Parse start and end times as moment.js objects
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

// helper for shift allocation
function set_shift_allocation(frm, fullName) {
    if (!frm.doc.shift_allocation) {
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
                fields: ['name']
            },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    frm.set_value('shift_allocation', r.message[0].name);
                } else {
                    frappe.msgprint(__('No allocated shifts found. Please contact the office.'));
                }
            }
        });
    }
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