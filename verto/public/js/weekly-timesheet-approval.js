frappe.ready(function () {
    const page = document.getElementById("grouped-timesheet-approval");
    if (!page) return;

    const urlParams = new URLSearchParams(window.location.search);
    const approvalToken = urlParams.get("token");

    const loadingElement = document.getElementById("grouped-loading");
    const errorElement = document.getElementById("grouped-error");
    const contentElement = document.getElementById("grouped-approval-content");
    const signatureSection = document.getElementById("grouped-signature-section");
    const signedPanel = document.getElementById("grouped-signed-panel");
    const partialPanel = document.getElementById("grouped-partial-panel");
    const submitButton = document.getElementById("grouped-submit-button");
    const downloadSection = document.getElementById("grouped-download-section");
    const downloadButton = document.getElementById("grouped-download-button");
    const rejectButton = document.getElementById("grouped-reject-button");
    const rejectedPanel = document.getElementById("grouped-rejected-panel");
    const rejectionDialog = document.getElementById("grouped-rejection-dialog");
    const rejectionConfirm = document.getElementById("grouped-rejection-confirm");
    const rejectionCancel = document.getElementById("grouped-rejection-cancel");
    let decisionPending = false;

    const canvas = document.getElementById("grouped-signature-pad");
    const context = canvas.getContext("2d");
    let drawing = false;
    let hasDrawnSignature = false;
    let lastPoint = null;
    let approvalData = null;

    initialiseSignaturePad();
    initialiseSignatureModeToggle();
    initialiseForm();

    if (!approvalToken) {
        showPageError("This weekly timesheet approval link is incomplete.");
        return;
    }

    loadGroupedTimesheets();

    function initialiseSignaturePad() {
        context.lineWidth = 4;
        context.lineCap = "round";
        context.lineJoin = "round";
        context.strokeStyle = "#111827";

        canvas.addEventListener("pointerdown", function (event) {
            event.preventDefault();
            drawing = true;
            hasDrawnSignature = true;
            lastPoint = getCanvasPoint(event);
            canvas.setPointerCapture(event.pointerId);

            // Draw a dot for a short tap/click.
            context.beginPath();
            context.arc(lastPoint.x, lastPoint.y, 2, 0, Math.PI * 2);
            context.fillStyle = "#111827";
            context.fill();
        });

        canvas.addEventListener("pointermove", function (event) {
            if (!drawing) return;
            event.preventDefault();

            const point = getCanvasPoint(event);
            context.beginPath();
            context.moveTo(lastPoint.x, lastPoint.y);
            context.lineTo(point.x, point.y);
            context.stroke();
            lastPoint = point;
        });

        ["pointerup", "pointercancel", "pointerleave"].forEach(function (eventName) {
            canvas.addEventListener(eventName, function (event) {
                if (!drawing) return;
                drawing = false;
                lastPoint = null;

                if (canvas.hasPointerCapture && canvas.hasPointerCapture(event.pointerId)) {
                    canvas.releasePointerCapture(event.pointerId);
                }
            });
        });

        document.getElementById("grouped-clear-button").addEventListener("click", clearSignature);
    }

    function getCanvasPoint(event) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: (event.clientX - rect.left) * (canvas.width / rect.width),
            y: (event.clientY - rect.top) * (canvas.height / rect.height)
        };
    }

    function clearSignature() {
        context.clearRect(0, 0, canvas.width, canvas.height);
        hasDrawnSignature = false;
        lastPoint = null;
    }

    function initialiseSignatureModeToggle() {
        document.querySelectorAll("input[name='grouped_sig_mode']").forEach(function (input) {
            input.addEventListener("change", function () {
                const drawWrapper = document.getElementById("grouped-draw-wrapper");
                const typeWrapper = document.getElementById("grouped-type-wrapper");

                drawWrapper.classList.toggle("gta-hidden", this.value !== "draw");
                typeWrapper.classList.toggle("gta-hidden", this.value !== "type");
            });
        });
    }

    function initialiseForm() {
        const now = new Date();
        const localDate = [
            now.getFullYear(),
            String(now.getMonth() + 1).padStart(2, "0"),
            String(now.getDate()).padStart(2, "0")
        ].join("-");

        document.getElementById("grouped-date-signed").value = localDate;
        submitButton.addEventListener("click", submitGroupedSignature);
        downloadButton.addEventListener("click", downloadSignedPdfs);
        rejectButton.addEventListener("click", function () {
            if (decisionPending || !approvalData || !approvalData.can_reject) return;
            document.getElementById("grouped-rejection-name").value = document.getElementById("grouped-full-name").value;
            document.getElementById("grouped-rejection-error").textContent = "";
            rejectionDialog.showModal();
        });
        rejectionCancel.addEventListener("click", () => rejectionDialog.close());
        rejectionDialog.addEventListener("cancel", event => {
            if (decisionPending) event.preventDefault();
        });
        document.getElementById("grouped-rejection-form").addEventListener("submit", submitRejection);
    }

    function loadGroupedTimesheets() {
        frappe.call({
            method: "verto.api.timesheet_signing.get_grouped_timesheets_public",
            args: { token: approvalToken },
            callback: function (response) {
                if (!response.message) {
                    showPageError("The weekly timesheets could not be loaded.");
                    return;
                }

                approvalData = response.message;
                renderApproval(approvalData);
            },
            error: function (response) {
                showPageError(getServerError(response) || "The approval link could not be loaded.");
            }
        });
    }

    function renderApproval(data) {
        loadingElement.classList.add("gta-hidden");
        errorElement.classList.add("gta-hidden");
        contentElement.classList.remove("gta-hidden");

        document.getElementById("grouped-project").textContent = data.project_name || data.project || "";
        document.getElementById("grouped-week").textContent = data.week_label || "";
        document.getElementById("grouped-employees").textContent = String(data.employee_count || 0);
        document.getElementById("grouped-hours").textContent = formatHours(data.totals.total);

        renderStatus(data);
        renderTimesheetTable(data);
        rejectButton.classList.toggle("gta-hidden", !data.can_reject);
        rejectedPanel.classList.add("gta-hidden");

        if (data.approval_status === "Rejected" || data.approval_status === "Superseded") {
            signatureSection.classList.add("gta-hidden");
            partialPanel.classList.add("gta-hidden");
            signedPanel.classList.add("gta-hidden");
            downloadSection.classList.add("gta-hidden");
            rejectedPanel.classList.remove("gta-hidden");
            const replaced = data.approval_status === "Superseded";
            document.getElementById("grouped-decision-heading").textContent = replaced
                ? "This approval request has been replaced."
                : "Rejected — awaiting correction.";
            document.getElementById("grouped-decision-note").textContent = replaced
                ? "Please use the link in the latest approval email to review the corrected week."
                : (data.notification_failed
                    ? "Your rejection is recorded, but its email could not be queued. Please contact the site team."
                    : "Your rejection is recorded. The site team will review your reason and resend the week when it is ready.");
            document.getElementById("grouped-rejection-by").textContent = data.rejected_by
                ? `Rejected by ${data.rejected_by}${data.rejected_on ? " on " + data.rejected_on : ""}.`
                : "";
            document.getElementById("grouped-rejection-reason").textContent = data.rejection_reason || "";
            return;
        }

        if (data.is_already_signed) {
            signatureSection.classList.add("gta-hidden");
            partialPanel.classList.add("gta-hidden");
            signedPanel.classList.remove("gta-hidden");
            downloadSection.classList.remove("gta-hidden");

            const signedBy = data.signed_by ? ` by ${escapeHtml(data.signed_by)}` : "";
            const signedDate = data.date_signed ? ` on ${escapeHtml(formatDate(data.date_signed))}` : "";
            signedPanel.innerHTML = `<strong>Approved.</strong> These weekly Timesheets were signed${signedBy}${signedDate}.`;
        } else if ((data.signed_count || 0) > 0) {
            signatureSection.classList.remove("gta-hidden");
            signedPanel.classList.add("gta-hidden");
            downloadSection.classList.add("gta-hidden");
            partialPanel.classList.remove("gta-hidden");
        } else {
            signatureSection.classList.remove("gta-hidden");
            signedPanel.classList.add("gta-hidden");
            downloadSection.classList.add("gta-hidden");
            partialPanel.classList.add("gta-hidden");
        }
    }

    function downloadSignedPdfs() {
        if (!approvalData || !approvalData.is_already_signed) {
            showModal("The PDF download will be available after all Timesheets are signed.");
            return;
        }

        downloadButton.disabled = true;
        downloadButton.textContent = "Preparing Download...";

        const method = "verto.api.timesheet_signing.download_grouped_signed_timesheets";
        const query = new URLSearchParams({ token: approvalToken });
        window.location.href = `/api/method/${method}?${query.toString()}`;

        window.setTimeout(function () {
            downloadButton.disabled = false;
            downloadButton.textContent = "Download Signed PDFs";
        }, 2500);
    }

    function renderStatus(data) {
        const badge = document.getElementById("grouped-status-badge");
        badge.textContent = data.approval_status || "Awaiting Signature";
        badge.classList.remove(
            "gta-status-awaiting",
            "gta-status-signed",
            "gta-status-partial",
            "gta-status-rejected"
        );

        if (data.approval_status === "Rejected" || data.approval_status === "Superseded") {
            badge.classList.add("gta-status-rejected");
        } else if (data.approval_status === "Signed") {
            badge.classList.add("gta-status-signed");
        } else if (data.approval_status === "Partially Signed") {
            badge.classList.add("gta-status-partial");
        } else {
            badge.classList.add("gta-status-awaiting");
        }
    }

    function renderTimesheetTable(data) {
        const table = document.getElementById("grouped-timesheet-table");
        const dates = data.dates || [];
        const employees = data.employees || [];

        let firstHeaderRow = `
            <tr>
                <th rowspan="2" class="gta-employee-head">Employee</th>
        `;

        dates.forEach(function (date) {
            firstHeaderRow += `
                <th colspan="2">
                    ${escapeHtml(date.day_short)}<br>
                    <small>${escapeHtml(date.label)}</small>
                </th>
            `;
        });

        firstHeaderRow += `
                <th colspan="3">Weekly Totals</th>
            </tr>
        `;

        let secondHeaderRow = "<tr>";
        dates.forEach(function () {
            secondHeaderRow += `
                <th class="gta-ds-head">DS</th>
                <th class="gta-ns-head">NS</th>
            `;
        });
        secondHeaderRow += `
            <th class="gta-ds-head">DS</th>
            <th class="gta-ns-head">NS</th>
            <th>Total</th>
        </tr>`;

        let bodyRows = "";

        employees.forEach(function (employee) {
            bodyRows += `
                <tr>
                    <td class="gta-employee-cell">
                        <span class="gta-employee-name">${escapeHtml(employee.employee_name || employee.employee || "")}</span>
                        ${employee.role ? `<span class="gta-role">${escapeHtml(employee.role)}</span>` : ""}
                    </td>
            `;

            dates.forEach(function (date) {
                const day = employee.days[date.date] || { ds: 0, ns: 0 };
                bodyRows += `
                    <td class="gta-ds-cell">${formatHours(day.ds, true)}</td>
                    <td class="gta-ns-cell">${formatHours(day.ns, true)}</td>
                `;
            });

            bodyRows += `
                    <td class="gta-ds-cell gta-total-cell">${formatHours(employee.total_ds, true)}</td>
                    <td class="gta-ns-cell gta-total-cell">${formatHours(employee.total_ns, true)}</td>
                    <td class="gta-total-cell">${formatHours(employee.total, true)}</td>
                </tr>
            `;
        });

        let totalsRow = `
            <tr class="gta-totals-row">
                <td class="gta-employee-cell">Project Totals</td>
        `;

        dates.forEach(function (date) {
            const totals = data.day_totals[date.date] || { ds: 0, ns: 0 };
            totalsRow += `
                <td class="gta-ds-cell">${formatHours(totals.ds, true)}</td>
                <td class="gta-ns-cell">${formatHours(totals.ns, true)}</td>
            `;
        });

        totalsRow += `
                <td class="gta-ds-cell">${formatHours(data.totals.ds, true)}</td>
                <td class="gta-ns-cell">${formatHours(data.totals.ns, true)}</td>
                <td>${formatHours(data.totals.total, true)}</td>
            </tr>
        `;

        table.innerHTML = `
            <thead>${firstHeaderRow}${secondHeaderRow}</thead>
            <tbody>${bodyRows}${totalsRow}</tbody>
        `;
    }

    function submitGroupedSignature() {
        if (decisionPending || !approvalData || approvalData.can_sign === false) return;
        if (!approvalData || approvalData.is_already_signed) {
            showModal("These weekly Timesheets have already been signed.");
            return;
        }

        const fullName = document.getElementById("grouped-full-name").value.trim();
        const dateSigned = document.getElementById("grouped-date-signed").value;
        const signatureMode = document.querySelector("input[name='grouped_sig_mode']:checked").value;

        if (!fullName || !dateSigned) {
            showModal("Please enter your full name and the date signed.");
            return;
        }

        let signatureData;

        if (signatureMode === "draw") {
            if (!hasDrawnSignature) {
                showModal("Please draw your signature before submitting.");
                return;
            }
            signatureData = canvas.toDataURL("image/png");
        } else {
            const typedName = document.getElementById("grouped-typed-name").value.trim();
            if (!typedName) {
                showModal("Please type your signature before submitting.");
                return;
            }
            signatureData = createTypedSignature(typedName);
        }

        setSubmitting(true);

        frappe.call({
            method: "verto.api.timesheet_signing.sign_grouped_timesheets",
            args: {
                token: approvalToken,
                signature_base64: signatureData,
                full_name: fullName,
                date_signed: dateSigned
            },
            callback: function (response) {
                const result = response.message || {};

                if (result.status === "Success") {
                    showModal("Weekly Timesheets approved successfully.", function () {
                        window.location.reload();
                    });
                    return;
                }

                if (result.status === "Already signed") {
                    showModal(result.message || "These weekly Timesheets have already been signed.", function () {
                        window.location.reload();
                    });
                    return;
                }

                setSubmitting(false);
                showModal(result.message || "The signature could not be submitted.");
            },
            error: function (response) {
                setSubmitting(false);
                showModal(getServerError(response) || "An error occurred while submitting the signature.");
            }
        });
    }

    function createTypedSignature(name) {
        const typedCanvas = document.getElementById("grouped-typed-canvas");
        const typedContext = typedCanvas.getContext("2d");
        typedContext.clearRect(0, 0, typedCanvas.width, typedCanvas.height);
        typedContext.fillStyle = "#111827";
        typedContext.textAlign = "center";
        typedContext.textBaseline = "middle";

        let fontSize = 88;
        do {
            typedContext.font = `${fontSize}px "Brush Script MT", "Segoe Script", cursive`;
            fontSize -= 2;
        } while (typedContext.measureText(name).width > typedCanvas.width - 80 && fontSize > 34);

        typedContext.fillText(name, typedCanvas.width / 2, typedCanvas.height / 2);
        return typedCanvas.toDataURL("image/png");
    }

    function setSubmitting(isSubmitting) {
        decisionPending = isSubmitting;
        submitButton.disabled = isSubmitting;
        rejectButton.disabled = isSubmitting;
        rejectionConfirm.disabled = isSubmitting;
        rejectionCancel.disabled = isSubmitting;
        rejectionConfirm.textContent = isSubmitting ? "Submitting..." : "Reject and Send Reason";
        submitButton.textContent = isSubmitting
            ? "Submitting Approval..."
            : "Approve and Sign Timesheets";
    }

    function submitRejection(event) {
        event.preventDefault();
        if (decisionPending || !approvalData || !approvalData.can_reject) return;
        const fullName = document.getElementById("grouped-rejection-name").value.trim();
        const reason = document.getElementById("grouped-rejection-input").value.trim();
        const error = document.getElementById("grouped-rejection-error");
        if (!fullName || !reason) {
            error.textContent = "Please enter your full name and a rejection reason.";
            return;
        }
        error.textContent = "";
        setSubmitting(true);
        frappe.call({
            method: "verto.api.timesheet_approval.reject_grouped_timesheets",
            type: "POST",
            args: {token: approvalToken, full_name: fullName, reason},
            callback(response) {
                const result = response.message || {};
                setSubmitting(false);
                if (result.status === "Rejected" || result.status === "Already rejected") {
                    rejectionDialog.close();
                    loadGroupedTimesheets();
                    showModal(result.message || "Your rejection has been recorded.");
                } else {
                    error.textContent = result.message || "The rejection could not be recorded. Please try again.";
                }
            },
            error(response) {
                setSubmitting(false);
                error.textContent = getServerError(response) || "The rejection could not be recorded. Please try again.";
            }
        });
    }

    function showPageError(message) {
        loadingElement.classList.add("gta-hidden");
        contentElement.classList.add("gta-hidden");
        errorElement.textContent = message;
        errorElement.classList.remove("gta-hidden");
    }

    function formatHours(value, showDashForZero) {
        const numericValue = Number(value || 0);
        if (showDashForZero && Math.abs(numericValue) < 0.0001) return "–";
        return numericValue.toFixed(2).replace(/\.00$/, "").replace(/(\.\d)0$/, "$1");
    }

    function formatDate(dateString) {
        if (!dateString) return "";
        const date = new Date(`${dateString}T00:00:00`);
        return date.toLocaleDateString("en-AU", {
            day: "2-digit",
            month: "short",
            year: "numeric"
        });
    }

    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function getServerError(response) {
        if (!response) return "";

        try {
            if (response._server_messages) {
                const messages = JSON.parse(response._server_messages);
                if (messages.length) {
                    const parsed = JSON.parse(messages[0]);
                    return parsed.message || parsed;
                }
            }

            if (response.responseJSON && response.responseJSON.exception) {
                return response.responseJSON.exception.split(":").pop().trim();
            }
        } catch (error) {
            return "";
        }

        return "";
    }

    function showModal(message, onClose) {
        const modal = document.getElementById("grouped-status-modal");
        const messageElement = document.getElementById("grouped-modal-message");
        const closeButton = document.getElementById("grouped-modal-close");

        messageElement.textContent = message;
        modal.classList.remove("gta-hidden");

        closeButton.onclick = function () {
            modal.classList.add("gta-hidden");
            closeButton.onclick = null;
            if (typeof onClose === "function") onClose();
        };
    }
});
