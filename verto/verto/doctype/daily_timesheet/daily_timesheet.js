// Copyright (c) 2026, Webwire and contributors
// For license information, please see license.txt

frappe.ui.form.on('Daily Timesheet', {
    start_time: function (frm) {
        calculate_duration(frm);
    },
    end_time: function (frm) {
        calculate_duration(frm);
    },
    date: function (frm) {
        if (frm.doc.current_user) {
            set_shift_allocation(frm, frm.doc.current_user);
        }
    },
    refresh: function (frm) {
        if (!frm.doc.current_user) {
            let currentUser = frappe.session.user;

            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'User',
                    filters: {
                        'name': currentUser
                    },
                    fieldname: ['full_name']
                },
                callback: function (r) {
                    if (r.message) {
                        let fullName = r.message.full_name;
                        frm.set_value('current_user', fullName);
                        set_shift_allocation(frm, fullName);
                    }
                }
            });
        } else {
            set_shift_allocation(frm, frm.doc.current_user);
        }

        if (!frm.doc.date) {
            let today = frappe.datetime.get_today();
            frm.set_value('date', today);
        }

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

    before_save: function (frm) {
        if (frm.skip_confirm) {
            frm.skip_confirm = false;
            return;
        }

        if (frm.doc.duration) {
            const hours = (frm.doc.duration / 3600).toFixed(2);

            frappe.validated = false;

            frappe.confirm(
                __("Your current hours for this shift is {0} hours. Is this correct?", [hours]),
                function () {
                    frm.skip_confirm = true;
                    frappe.validated = true;
                    frm.save();
                },
                function () {
                    frappe.validated = false;
                }
            );
        }
    },

    after_save: async function (frm) {
        try {
            await mark_attendance_from_timesheet(frm);
        } catch (e) {
            console.error("Attendance marking failed", e);
        }

        setTimeout(() => {
            window.location.href = '/app/shifts';
        }, 2000);
    }
});

function calculate_duration(frm) {
    if (frm.doc.start_time && frm.doc.end_time) {
        var start_time = moment(frm.doc.start_time, 'HH:mm:ss');
        var end_time = moment(frm.doc.end_time, 'HH:mm:ss');

        if (end_time.isBefore(start_time)) {
            end_time.add(1, 'day');
        }

        var duration_ms = end_time.diff(start_time);
        var duration_seconds = duration_ms / 1000;
        frm.set_value('duration', duration_seconds);
    }
}

// Fetch a single Shift Assignment record (or null)
function fetch_one_shift_assignment({
    fullName,
    filters,
    order_by
}) {
    return new Promise((resolve, reject) => {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Shift Assignment",
                fields: ["name", "start_date", "end_date"],
                filters: [
                    ["employee_name", "=", fullName],
                    ["docstatus", "=", 1],
                    ...filters,
                ],
                order_by: order_by || "",
                limit_page_length: 1,
            },
            callback: (r) => resolve((r.message && r.message[0]) || null),
            error: (e) => reject(e),
        });
    });
}

async function set_shift_allocation(frm, fullName) {
    if (frm.doc.shift_allocation) return;

    const d = frm.doc.date;
    if (!d || !fullName) return;

    const current = await fetch_one_shift_assignment({
        fullName,
        filters: [
            ["start_date", "<=", d],
            ["end_date", ">=", d],
        ],
        order_by: "start_date desc",
    });

    if (current) {
        await frm.set_value("shift_allocation", current.name);
        return;
    }

    const [prev, next] = await Promise.all([
        fetch_one_shift_assignment({
            fullName,
            filters: [
                ["end_date", "<", d]
            ],
            order_by: "end_date desc",
        }),
        fetch_one_shift_assignment({
            fullName,
            filters: [
                ["start_date", ">", d]
            ],
            order_by: "start_date asc",
        }),
    ]);

    let chosen = null;

    if (prev && next) {
        const prevDiffDays = Math.abs(frappe.datetime.get_diff(d, prev.end_date));
        const nextDiffDays = Math.abs(frappe.datetime.get_diff(next.start_date, d));
        chosen = prevDiffDays <= nextDiffDays ? prev : next;
    } else {
        chosen = prev || next;
    }

    if (chosen) {
        await frm.set_value("shift_allocation", chosen.name);
    } else {
        frappe.msgprint(__("No allocated shifts found (including nearest). Please contact the office."));
    }
}

async function mark_attendance_from_timesheet(frm) {
    if (!frm.doc.date || !frm.doc.shift_allocation) {
        return;
    }

    // Prevent duplicate processing in the same form session
    if (frm.__attendance_marked_for === frm.doc.date) {
        return;
    }

    const shift = await frappe.db.get_doc("Shift Assignment", frm.doc.shift_allocation);
    if (!shift || !shift.employee) {
        frappe.msgprint(__("Unable to mark attendance because no Employee was found on the Shift Allocation."));
        return;
    }

    // Check if attendance already exists for this employee/date
    const existing = await frappe.db.get_list("Attendance", {
        fields: ["name", "docstatus", "status"],
        filters: {
            employee: shift.employee,
            attendance_date: frm.doc.date
        },
        limit: 1
    });

    if (existing && existing.length) {
        // Optional: update draft attendance if needed
        if (existing[0].docstatus === 0 && existing[0].status !== "Present") {
            await frappe.db.set_value("Attendance", existing[0].name, "status", "Present");
        }

        frm.__attendance_marked_for = frm.doc.date;
        return;
    }

    // Create new attendance record
    const inserted = await frappe.call({
        method: "frappe.client.insert",
        args: {
            doc: {
                doctype: "Attendance",
                employee: shift.employee,
                employee_name: shift.employee_name,
                attendance_date: frm.doc.date,
                status: "Present",
                shift: shift.shift_type || shift.shift || undefined,
                company: shift.company || undefined
            }
        }
    });

    // Submit the attendance record
    if (inserted.message && inserted.message.name) {
        await frappe.call({
            method: "frappe.client.submit",
            args: {
                doc: inserted.message
            }
        });
    }

    frm.__attendance_marked_for = frm.doc.date;
}