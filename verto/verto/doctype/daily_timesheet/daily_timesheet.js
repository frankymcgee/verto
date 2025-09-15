// Copyright (c) 2024, Webwire and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Daily Timesheet", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Daily Timesheet', {
    refresh: function(frm) {
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
    after_save: function(frm) {        
        setTimeout(() => {window.location.href = '/app/shifts';}, 2000);  // Redirect after 2 seconds
    }
});

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