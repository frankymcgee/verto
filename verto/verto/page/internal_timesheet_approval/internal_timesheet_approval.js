frappe.pages["internal-timesheet-approval"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Internal Timesheet Approval"), single_column: true });
    wrapper.internal_review = new frappe.InternalTimesheetReview(page);
};
frappe.pages["internal-timesheet-approval"].on_page_show = function (wrapper) {
    wrapper.internal_review.show();
};

frappe.InternalTimesheetReview = class {
    constructor(page) {
        this.root = document.createElement("div");
        this.root.className = "ita-review";
        page.body.append(this.root);
        this.root.innerHTML = `
          <style>
            .ita-review { padding:16px; color:var(--text-color,#17212b); }
            .ita-review * { box-sizing:border-box; }
            .ita-review h2,.ita-review h3 { margin:0 0 8px; }
            .ita-card { border:1px solid var(--border-color,#dce3ea); border-radius:12px; background:var(--card-bg,#fff); padding:18px; margin-bottom:18px; }
            .ita-filters { display:flex; gap:16px; flex-wrap:wrap; align-items:end; }
            .ita-filters .form-group { margin-bottom:0; }
            .ita-filters label,.ita-field { display:flex; flex-direction:column; gap:6px; font-size:13px; }
            .ita-project { min-width:220px; flex:1; max-width:350px; }
            .ita-review input[type=date],.ita-review input[type=text],.ita-review textarea { border:1px solid var(--border-color,#dce3ea); border-radius:8px; background:var(--control-bg,#f8fafc); color:inherit; padding:8px 10px; }
            .ita-tools,.ita-metrics { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:14px 0; }
            .ita-metrics span { border:1px solid var(--border-color,#dce3ea); border-radius:8px; padding:10px 14px; }
            .ita-group-header { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; }
            .ita-table-wrap { overflow:auto; border:1px solid var(--border-color,#dce3ea); border-radius:8px; }
            .ita-matrix { min-width:1280px; width:100%; border-collapse:separate; border-spacing:0; font-size:12px; }
            .ita-matrix th,.ita-matrix td { padding:9px 6px; text-align:center; border-right:1px solid var(--border-color,#dce3ea); border-bottom:1px solid var(--border-color,#dce3ea); }
            .ita-matrix thead th { background:var(--subtle-fg,#f8fafc); }
            .ita-matrix .ita-person { text-align:left; width:240px; min-width:240px; position:sticky; left:0; background:var(--card-bg,#fff); z-index:1; }
            .ita-matrix thead .ita-person { z-index:2; }
            .ita-ds { background:color-mix(in srgb,#0284c7 7%,var(--card-bg,#fff)); }
            .ita-ns { background:color-mix(in srgb,#7c3aed 7%,var(--card-bg,#fff)); }
            .ita-flag-cell { box-shadow:inset 0 -3px #d97706; }
            .ita-flag { color:var(--text-color,#17212b); border-left:3px solid #d97706; background:color-mix(in srgb,#f59e0b 10%,var(--card-bg,#fff)); padding:8px 12px; margin:6px 0; }
            .ita-clean { color:#13834b; }
            .ita-muted { color:var(--text-muted,#64748b); font-size:12px; }
            .ita-details { margin-top:14px; border-top:1px solid var(--border-color,#dce3ea); padding-top:10px; }
            .ita-details summary { cursor:pointer; font-weight:600; padding:8px 0; }
            .ita-entry { border:1px solid var(--border-color,#dce3ea); padding:14px; border-radius:8px; margin:10px 0; }
            .ita-entry-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; font-size:13px; }
            .ita-entry-grid strong { display:block; }
            .ita-comments { white-space:pre-wrap; overflow-wrap:anywhere; margin-top:10px; font-size:13px; }
            .ita-check { display:flex; gap:8px; align-items:center; margin:10px 0; }
            .ita-signature-grid { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
            .ita-canvas { width:100%; max-width:800px; height:180px; background:#fff; border:1px solid var(--border-color,#dce3ea); border-radius:8px; touch-action:none; }
            .ita-error { color:#b42318; white-space:pre-wrap; }
            .ita-status { margin:14px 0; }
            .ita-hidden { display:none!important; }
            @media(max-width:700px) { .ita-review { padding:8px; } .ita-signature-grid { grid-template-columns:1fr; } .ita-entry-grid { grid-template-columns:1fr 1fr; } .ita-card { padding:12px; } }
          </style>
          <section class="ita-card">
            <h2>Review daily hours before internal approval</h2>
            <p class="ita-muted">Review all employees by project and week. Open an entry to inspect start/end times, allocations and comments. DS/NS from entered times follows the existing 16:30 start-time cutoff.</p>
            <div class="ita-filters">
              <label>Week beginning (Monday)<input type="date" data-week></label>
              <div class="ita-project" data-project></div>
              <label class="ita-check"><span><input type="checkbox" data-include-approved> Include internally approved</span></label>
              <button type="button" class="btn btn-primary" data-load>Review week</button>
            </div>
            <p class="ita-muted" data-scope></p>
            <div class="ita-metrics" data-metrics></div>
            <div class="ita-tools">
              <button type="button" class="btn btn-default" data-select-clean>Select clean timesheets</button>
              <button type="button" class="btn btn-default" data-select-all>Select all pending</button>
              <button type="button" class="btn btn-default" data-select-none>Clear selection</button>
              <strong data-selected>0 selected</strong>
            </div>
            <div class="ita-status" role="status" aria-live="polite" data-status></div>
          </section>
          <div data-results></div>
          <section class="ita-card ita-hidden" data-signing>
            <h3>Sign selected timesheets</h3>
            <p class="ita-muted">One signature approves only the selected timesheets. Already approved records keep their existing internal signature.</p>
            <div class="ita-signature-grid">
              <div>
                <label class="ita-field">Signatory name<input type="text" maxlength="140" data-name autocomplete="name"></label>
                <div class="ita-check">
                  <label><input type="radio" name="internal-signature-mode" value="draw" checked> Draw signature</label>
                  <label><input type="radio" name="internal-signature-mode" value="type"> Type signature</label>
                </div>
                <div data-draw-wrapper>
                  <canvas width="800" height="240" class="ita-canvas" data-canvas aria-label="Draw your internal approval signature"></canvas>
                  <button type="button" class="btn btn-default btn-sm" data-clear-signature>Clear signature</button>
                </div>
                <p class="ita-muted ita-hidden" data-type-wrapper>Your signatory name will be rendered as the signature.</p>
                <canvas width="800" height="240" class="ita-hidden" data-typed-canvas></canvas>
              </div>
              <div>
                <div data-flag-review class="ita-hidden">
                  <p class="ita-flag" data-selected-flags></p>
                  <label class="ita-check"><input type="checkbox" data-acknowledge> I have reviewed the selected validation flags.</label>
                  <label class="ita-field">Review note<textarea rows="4" maxlength="4000" data-review-note placeholder="Explain why the flagged hours can be approved, or exclude them and correct the records."></textarea></label>
                </div>
                <p class="ita-muted">Approval is recorded against your signed-in user and the current server date.</p>
                <button type="button" class="btn btn-primary" data-approve>Approve selected timesheets</button>
              </div>
            </div>
          </section>`;
        this.data = null;
        this.rows = [];
        this.selected = new Set();
        this.explicitNames = null;
        this.busy = false;
        this.sequence = 0;
        this.drawn = false;
        this.project = frappe.ui.form.make_control({ parent: this.find("project"), df: { fieldname: "project", fieldtype: "Link", options: "Project", label: "Project (blank for all)", placeholder: "All projects" }, render_input: true });
        this.find("load").addEventListener("click", () => { this.explicitNames = null; this.load(); });
        this.find("select-clean").addEventListener("click", () => this.selectRows(false));
        this.find("select-all").addEventListener("click", () => this.selectRows(true));
        this.find("select-none").addEventListener("click", () => { this.selected.clear(); this.updateSelection(); });
        this.find("approve").addEventListener("click", () => this.approve());
        this.find("clear-signature").addEventListener("click", () => this.clearSignature());
        this.root.addEventListener("change", event => {
            if (this.busy) return;
            if (event.target.dataset.timesheet) {
                if (event.target.checked) this.selected.add(event.target.dataset.timesheet);
                else this.selected.delete(event.target.dataset.timesheet);
                this.updateSelection();
            }
            if (event.target.name === "internal-signature-mode") {
                const draw = event.target.value === "draw";
                this.find("draw-wrapper").classList.toggle("ita-hidden", !draw);
                this.find("type-wrapper").classList.toggle("ita-hidden", draw);
            }
        });
        this.initialisePad();
    }

    find(name) { return this.root.querySelector(`[data-${name}]`); }
    escape(value) { return String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]); }
    hours(value) { return Number(value || 0).toFixed(2); }
    date(value) { return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" }); }
    link(doctype, name, label) { return `<a href="/app/${doctype}/${encodeURIComponent(name)}" target="_blank" rel="noopener">${this.escape(label || name)}</a>`; }
    message(text, error = false) { this.find("status").textContent = text; this.find("status").classList.toggle("ita-error", error); }

    show() {
        const options = frappe.route_options || {};
        const query = new URLSearchParams(window.location.search);
        let names = options.timesheets || query.get("timesheets");
        if (typeof names === "string") { try { names = JSON.parse(names); } catch { names = null; } }
        if (Array.isArray(names) && names.length) this.explicitNames = names;
        if (options.timesheets) frappe.route_options = null;
        if (!this.find("week").value) {
            const today = new Date(`${frappe.datetime.get_today()}T12:00:00`);
            today.setDate(today.getDate() - ((today.getDay() + 6) % 7) - 7);
            this.find("week").value = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
        }
        this.load();
    }

    lock(value) {
        this.busy = value;
        if (value) {
            this.disabled = new Map([...this.root.querySelectorAll("input,button,textarea")].map(element => [element, element.disabled]));
            this.disabled.forEach((_, element) => { element.disabled = true; });
        } else {
            this.disabled?.forEach((disabled, element) => { element.disabled = disabled; });
            this.updateSelection();
        }
    }

    load() {
        if (this.busy) return;
        const sequence = ++this.sequence;
        this.lock(true);
        this.data = null;
        this.rows = [];
        this.selected.clear();
        this.find("signing").classList.add("ita-hidden");
        this.find("results").innerHTML = "";
        this.find("metrics").innerHTML = "";
        this.find("selected").textContent = "0 selected";
        this.message("Loading timesheets…");
        const args = this.explicitNames ? { timesheets: this.explicitNames } : {
            week_start: this.find("week").value, project: this.project.get_value() || "", include_approved: this.find("include-approved").checked ? 1 : 0,
        };
        frappe.call({ method: "verto.api.internal_timesheet_approval.get_internal_timesheet_review", args,
            callback: response => {
                if (sequence !== this.sequence) return;
                if (!response.message) { this.message("The timesheets could not be loaded.", true); this.lock(false); return; }
                this.data = response.message;
                this.rows = this.data.groups.flatMap(group => group.rows);
                this.render();
                this.lock(false);
                this.selectRows(false);
                this.message(this.rows.length ? "Clean timesheets are selected. Review flagged entries before adding them to your approval." : "No timesheets match this review.");
            },
            error: response => { this.message(this.errorMessage(response), true); this.lock(false); },
        });
    }

    render() {
        this.find("scope").textContent = this.explicitNames ? "Reviewing the exact Timesheets selected from the list. Use Review week to show everyone for a project/week." : "Showing all permitted Timesheets for the selected week and project.";
        this.find("metrics").innerHTML = `<span><strong>${this.data.timesheet_count}</strong> timesheets</span><span><strong>${this.data.pending_count}</strong> awaiting approval</span><span><strong>${this.data.flagged_count}</strong> with flags</span>`;
        if (!this.find("name").value) this.find("name").value = this.data.signer_name;
        this.find("results").innerHTML = this.data.groups.map(group => this.renderGroup(group)).join("");
        this.find("signing").classList.toggle("ita-hidden", !this.rows.some(row => row.can_approve && !row.internal_approved));
    }

    renderGroup(group) {
        const rows = [...group.rows].sort((a, b) => String(a.employee_name).localeCompare(String(b.employee_name)));
        const heading = `<tr><th rowspan="2" class="ita-person">Employee / timesheet</th>${group.dates.map(date => `<th colspan="2">${this.escape(new Date(`${date}T12:00:00`).toLocaleDateString(undefined, { weekday: "short" }))}<br>${this.date(date)}</th>`).join("")}<th rowspan="2">Total</th></tr><tr>${group.dates.map(() => '<th class="ita-ds">DS</th><th class="ita-ns">NS</th>').join("")}</tr>`;
        const body = rows.map(row => `<tr><td class="ita-person"><label class="ita-check"><input type="checkbox" data-timesheet="${this.escape(row.name)}" ${row.internal_approved || !row.can_approve ? "disabled" : ""}><strong>${this.escape(row.employee_name)}</strong></label>${this.link("timesheet", row.name)}<div class="ita-muted">${this.escape(row.role)} · ${row.docstatus === 1 ? "Submitted" : "Draft"}</div><div class="${row.flag_count ? "" : "ita-clean"}">${row.internal_approved ? `Approved by ${this.escape(row.approved_by)}` : !row.can_approve ? "Read only" : row.flag_count ? `${row.flag_count} validation flags` : "Checks passed"}</div></td>${group.dates.map(date => { const day = row.days[date]; const flag = day.flag_count ? " ita-flag-cell" : ""; const allocation = day.allocations.join(", "); return `<td class="ita-ds${flag}" title="${this.escape(allocation)}">${this.hours(day.ds)}</td><td class="ita-ns${flag}" title="${this.escape(allocation)}">${this.hours(day.ns)}</td>`; }).join("")}<td><strong>${this.hours(row.total)}</strong></td></tr>`).join("");
        const totals = group.dates.map(date => `<td>${this.hours(rows.reduce((sum, row) => sum + row.days[date].ds, 0))}</td><td>${this.hours(rows.reduce((sum, row) => sum + row.days[date].ns, 0))}</td>`).join("");
        return `<section class="ita-card"><div class="ita-group-header"><h3>${this.escape(group.project_name)}</h3><span>${this.date(group.week_start)} – ${this.date(group.week_end)}</span></div><div class="ita-table-wrap"><table class="ita-matrix"><thead>${heading}</thead><tbody>${body}</tbody><tfoot><tr><th class="ita-person">Project / week totals</th>${totals}<th>${this.hours(group.total)}</th></tr></tfoot></table></div>${rows.map(row => this.renderDetails(row)).join("")}</section>`;
    }

    renderDetails(row) {
        return `<details class="ita-details" ${row.flag_count ? "open" : ""}><summary>${this.escape(row.employee_name)} · ${this.escape(row.name)} · ${row.flag_count ? `${row.flag_count} flags` : "Hours and comments"}</summary>${row.flags.map(flag => `<p class="ita-flag">${this.escape(flag.message)}</p>`).join("")}${row.note ? `<p class="ita-comments"><strong>Weekly note:</strong> ${this.escape(row.note)}</p>` : ""}${row.entries.map(entry => `<article class="ita-entry"><h4>${this.date(entry.date)} · ${this.hours(entry.hours)} hours</h4><div class="ita-entry-grid"><div><strong>Allocated shift</strong>${this.escape(entry.allocated_shift || "No matching allocation")}${entry.allocation ? `<br>${this.link("shift-assignment", entry.allocation, "View allocation")}` : ""}</div><div><strong>Recorded / actual shift</strong>${this.escape(entry.declared_shift || "Unknown")} / ${this.escape(entry.recorded_shift || "Unknown")}</div><div><strong>Start</strong>${this.escape(entry.from_time)}</div><div><strong>End</strong>${this.escape(entry.to_time)}</div></div>${entry.flags.map(flag => `<p class="ita-flag">${this.escape(flag.message)}</p>`).join("")}<div class="ita-comments"><strong>Comments:</strong> ${this.escape(entry.comments || entry.daily_comments || "—")}</div>${entry.daily_comments && entry.daily_comments !== entry.comments ? `<div class="ita-comments"><strong>Current daily comments:</strong> ${this.escape(entry.daily_comments)}</div>` : ""}${entry.daily_timesheet ? `<p>${this.link("daily-timesheet", entry.daily_timesheet, "Open Daily Timesheet")}</p>` : ""}</article>`).join("")}</details>`;
    }

    selectRows(includeFlagged) {
        if (this.busy) return;
        this.selected = new Set(this.rows.filter(row => row.can_approve && !row.internal_approved && (includeFlagged || !row.flag_count)).map(row => row.name));
        this.updateSelection();
    }

    updateSelection() {
        const selected = this.rows.filter(row => this.selected.has(row.name) && row.can_approve && !row.internal_approved);
        this.root.querySelectorAll("[data-timesheet]").forEach(input => { input.checked = this.selected.has(input.dataset.timesheet); });
        const flagged = selected.filter(row => row.flag_count);
        this.find("selected").textContent = `${selected.length} selected · ${this.hours(selected.reduce((sum, row) => sum + row.total, 0))} hours`;
        this.find("flag-review").classList.toggle("ita-hidden", !flagged.length);
        this.find("selected-flags").textContent = `${flagged.length} selected timesheets have validation flags. Review them and record the reason for approval.`;
        this.find("approve").disabled = this.busy || !selected.length;
    }

    initialisePad() {
        const canvas = this.find("canvas"), context = canvas.getContext("2d");
        context.lineWidth = 4; context.lineCap = "round"; context.lineJoin = "round"; context.strokeStyle = "#111827";
        let previous = null;
        const point = event => { const rect = canvas.getBoundingClientRect(); return { x: (event.clientX - rect.left) * canvas.width / rect.width, y: (event.clientY - rect.top) * canvas.height / rect.height }; };
        canvas.addEventListener("pointerdown", event => {
            if (this.busy) return;
            event.preventDefault(); previous = point(event); this.drawn = true;
            canvas.setPointerCapture?.(event.pointerId);
            context.beginPath(); context.arc(previous.x, previous.y, 2, 0, 2 * Math.PI); context.fillStyle = "#111827"; context.fill();
        });
        canvas.addEventListener("pointermove", event => { if (!previous || this.busy) return; event.preventDefault(); const next = point(event); context.beginPath(); context.moveTo(previous.x, previous.y); context.lineTo(next.x, next.y); context.stroke(); previous = next; });
        ["pointerup", "pointercancel", "pointerleave"].forEach(name => canvas.addEventListener(name, event => { previous = null; if (canvas.hasPointerCapture?.(event.pointerId)) canvas.releasePointerCapture(event.pointerId); }));
    }

    clearSignature() { const canvas = this.find("canvas"); canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height); this.drawn = false; }

    signature(mode, name) {
        if (mode === "draw") return this.drawn ? this.find("canvas").toDataURL("image/png") : null;
        const canvas = this.find("typed-canvas"), context = canvas.getContext("2d");
        context.clearRect(0, 0, canvas.width, canvas.height); context.fillStyle = "#111827"; context.textAlign = "center"; context.textBaseline = "middle";
        let size = 86;
        do { context.font = `${size}px "Brush Script MT", "Segoe Script", cursive`; size -= 2; } while (context.measureText(name).width > canvas.width - 60 && size > 24);
        context.fillText(name, canvas.width / 2, canvas.height / 2);
        return canvas.toDataURL("image/png");
    }

    approve() {
        if (this.busy || !this.data) return;
        const selected = this.rows.filter(row => this.selected.has(row.name) && row.can_approve && !row.internal_approved);
        if (!selected.length) return this.message("Select at least one Timesheet.", true);
        const name = this.find("name").value.trim();
        if (!name) return this.message("Enter the signatory name.", true);
        const flagged = selected.some(row => row.flag_count);
        const note = this.find("review-note").value.trim();
        const acknowledged = this.find("acknowledge").checked;
        if (flagged && (!acknowledged || !note)) return this.message("Review the selected flags, tick the confirmation and enter a review note, or exclude those timesheets.", true);
        const mode = this.root.querySelector('input[name="internal-signature-mode"]:checked').value;
        const signature = this.signature(mode, name);
        if (!signature) return this.message("Draw your signature or choose Type signature.", true);
        this.lock(true); this.message(`Approving ${selected.length} timesheets…`);
        frappe.call({ method: "verto.api.internal_timesheet_approval.approve_internal_timesheets", type: "POST", args: {
            selections: selected.map(row => ({ name: row.name, review_hash: row.review_hash })), review_timesheets: this.rows.map(row => row.name),
            signature_dataurl: signature, signature_mode: mode, full_name: name, acknowledge_flags: acknowledged ? 1 : 0, review_note: note,
        }, callback: response => {
            this.lock(false);
            if (!response.message) return this.message("Approval did not return a result. Reload before trying again.", true);
            const count = response.message.approved.length;
            frappe.show_alert({ message: `${count} timesheets internally approved.`, indicator: "green" });
            this.clearSignature(); this.find("acknowledge").checked = false; this.find("review-note").value = "";
            this.load();
        }, error: response => { this.lock(false); this.message(this.errorMessage(response), true); } });
    }

    errorMessage(response) {
        const text = response?.responseJSON?.exception || response?.exception || "The request failed. Reload the review and try again.";
        return String(text).replace(/^.*(?:ValidationError|PermissionError):\s*/, "");
    }
};
