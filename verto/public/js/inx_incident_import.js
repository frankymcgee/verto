frappe.provide("verto.inx_incidents");

verto.inx_incidents.open_import = function (on_complete) {
    const method = "verto.api.inx_incident_import.import_inx_export";
    new frappe.ui.FileUploader({
        dialog_title: __("Import INX Summary Events Export"),
        allow_multiple: false,
        make_attachments_public: false,
        allow_toggle_private: false,
        allow_web_link: false,
        allow_google_drive: false,
        disable_file_browser: true,
        restrictions: { allowed_file_types: [".xlsx"], max_file_size: 10 * 1024 * 1024 },
        on_success: async (file) => {
            const response = await frappe.call({
                method, args: { file_name: file.name, dry_run: true },
                freeze: true, freeze_message: __("Checking the INX export…"),
            });
            const preview = response.message;
            if (!preview) return;
            const escape = frappe.utils.escape_html;
            const counts = [
                [__("Events in export"), preview.row_count],
                [__("New source incidents"), preview.new_sources],
                [__("Changed source incidents"), preview.changed_sources],
                [__("Unchanged source incidents"), preview.unchanged_sources],
                [__("New draft lessons"), preview.new_lessons],
                [__("Enabled lessons returning to review"), preview.enabled_lessons_returning_to_review],
                [__("Events without a Review Summary"), preview.missing_review_summaries],
            ];
            const html = `<table class="table table-bordered"><tbody>${counts.map(([label, value]) =>
                `<tr><td>${escape(label)}</td><td>${escape(String(value))}</td></tr>`).join("")}</tbody></table>
                <p>${escape(__("New and changed incidents remain unavailable to PERI until their crew-facing lessons are reviewed and enabled."))}</p>
                <p>${escape(__("This report contains immediate actions, not investigation action records. Investigation actions and controls are left blank."))}</p>
                <p>${escape(__("Columns excluded from import:"))} ${escape(preview.ignored_columns.join(", ") || __("None"))}</p>`;
            const dialog = new frappe.ui.Dialog({
                title: __("INX Import Preview"),
                fields: [
                    { fieldname: "preview", fieldtype: "HTML", options: html },
                    {
                        fieldname: "prepare_drafts", fieldtype: "Check",
                        label: __("Prepare Sanitised Drafts"), default: 1,
                        description: __("Masks known personnel names and contact details locally, then sends remaining text to Raven's configured OpenAI account to identify further personal information. Populates Source Site, What Happened and Immediate Response Recorded. Human review is required."),
                    },
                ],
                primary_action_label: __("Import Draft Lessons"),
                primary_action: async () => {
                    const button = dialog.get_primary_btn();
                    button.prop("disabled", true);
                    try {
                        const imported = await frappe.call({
                            method,
                            args: {
                                file_name: file.name, dry_run: false, expected_sha256: preview.file_sha256,
                                prepare_drafts: Boolean(dialog.get_value("prepare_drafts")),
                            },
                            freeze: true, freeze_message: __("Importing INX incidents…"),
                        });
                        if (!imported.message) return;
                        dialog.hide();
                        frappe.msgprint({
                            title: __("INX Import Complete"),
                            message: __("Processed {0} incidents; queued {1} sanitised drafts. Refresh the learning records to see their preparation status. Review each draft before enabling Available for JHA.", [imported.message.row_count, imported.message.sanitised_drafts_queued || 0]),
                            indicator: "green",
                        });
                        on_complete?.();
                    } finally {
                        button.prop("disabled", false);
                    }
                },
            });
            dialog.show();
        },
    });
};

verto.inx_incidents.prepare_drafts = function (names, on_complete) {
    const dialog = new frappe.ui.Dialog({
        title: __("Prepare Sanitised INX Drafts"),
        fields: [{
            fieldname: "notice", fieldtype: "HTML",
            options: frappe.utils.escape_html(__("Prepare the selected INX drafts, or all unprepared INX drafts when none are selected (up to 2,000). Source Site uses Location; What Happened uses Detailed Observation; Immediate Response Recorded uses Immediate Action Taken. Known personnel names and contact details are masked locally. Remaining text is sent to Raven's configured OpenAI account to identify further personal information. Existing wording is retained except for redactions. Review the results for missed identifiers and safety facts before enabling them for PERI.")),
        }],
        primary_action_label: __("Prepare Drafts"),
        primary_action: async () => {
            const button = dialog.get_primary_btn();
            button.prop("disabled", true);
            try {
                const response = await frappe.call({
                    method: "verto.api.inx_incident_sanitisation.prepare_inx_drafts",
                    args: { names }, freeze: true, freeze_message: __("Queuing draft preparation…"),
                });
                if (!response.message) return;
                dialog.hide();
                frappe.msgprint(__("Queued {0} drafts; skipped {1} records. Refresh to see preparation status. Prepared drafts still require review.", [response.message.queued, response.message.skipped]));
                on_complete?.();
            } finally {
                button.prop("disabled", false);
            }
        },
    });
    dialog.show();
};
