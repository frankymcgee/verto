from __future__ import annotations

import frappe


PRINT_FORMAT_NAME = "Digital JHA Workpack"
JHA_DOCTYPE = "Digital Job Hazard Analysis"

PRINT_HTML = r"""
{% set present_people = doc.participants | selectattr('present_for_discussion') | list %}
{% set critical_rows = doc.hazards_and_controls | selectattr('critical_risk') | list %}
{% set permit_rows = doc.hazards_and_controls | selectattr('permit_or_ccv_required') | list %}
{% set matrix_pages = ((doc.work_steps|length + 1) // 2) if doc.work_steps else 1 %}
{% set total_pages = matrix_pages + 4 %}

{% macro page_footer(page_no) -%}
<div class="page-footer">
  <span>THIS DOCUMENT IS UNCONTROLLED IN HARD COPY FORMAT</span>
  <span>{{ doc.name }} &nbsp; | &nbsp; Rev {{ doc.revision or 1 }} &nbsp; | &nbsp; {{ doc.jha_status }} &nbsp; | &nbsp; Page {{ page_no }} of {{ total_pages }}</span>
</div>
{%- endmacro %}

<div class="jha-pack">
  <section class="pack-page cover-page">
    <div class="page-title">
      <div>
        <h1>Job Hazard Analysis - Form</h1>
        <div class="subtitle">Health and Safety</div>
      </div>
      <div class="brand">MINE SITE SUPPORT</div>
    </div>

    <table class="form-grid context-grid">
      <tr>
        <th>Company:</th>
        <td>Mine Site Support</td>
        <th>Work Order #:</th>
        <td>{{ doc.work_order_number or '' }}</td>
        <th>Date:</th>
        <td>{{ frappe.utils.formatdate(doc.creation) if doc.creation else '' }}</td>
      </tr>
      <tr>
        <th>Location / work area:</th>
        <td>{{ doc.work_area or '' }}</td>
        <th>JHA #:</th>
        <td>{{ doc.name }}</td>
        <th>Project:</th>
        <td>{{ doc.project or '' }}</td>
      </tr>
      <tr>
        <td colspan="6" class="task-box">
          <strong>What is the task:</strong>
          <div>{{ doc.work_summary_title or doc.work_summary or '' }}</div>
        </td>
      </tr>
    </table>

    <div class="critical-summary">
      <strong>Critical Risk Management:</strong>
      Is a critical risk involved in this task?
      <span class="check-box">{% if critical_rows|length %}X{% endif %}</span> Yes
      <span class="check-box">{% if not critical_rows|length %}X{% endif %}</span> No
      <span class="prompt-note">If yes, review the applicable critical controls before work starts.</span>
    </div>

    <div class="risk-strip">
      {% if critical_rows|length %}
        {% for row in critical_rows[:8] %}
          <div class="risk-chip">
            <strong>{{ (row.hazard_or_energy_source or 'Critical Risk') | truncate(48, True, '...') }}</strong>
            {% if row.critical_control %}
              <span>{{ row.critical_control | truncate(65, True, '...') }}</span>
            {% endif %}
          </div>
        {% endfor %}
        {% if critical_rows|length > 8 %}
          <div class="risk-chip"><strong>+ {{ critical_rows|length - 8 }} additional critical risk(s)</strong></div>
        {% endif %}
      {% else %}
        <div class="empty-strip">No critical risks have been marked in the digital JHA.</div>
      {% endif %}
    </div>

    <div class="section-bar">Additional Permits / Clearances</div>
    <div class="permit-grid">
      {% if permit_rows|length %}
        {% for row in permit_rows[:12] %}
          <div class="permit-item"><span class="check-box">X</span>{{ row.permit_or_ccv_required | truncate(68, True, '...') }}</div>
        {% endfor %}
      {% else %}
        {% for label in ['Confined Space Entry', 'Hot Work', 'Critical Lift Plan', 'High Voltage Vicinity', 'Excavation / Penetration', 'Work at Height', 'Electrical Energised Work', 'Environmental'] %}
          <div class="permit-item"><span class="check-box"></span>{{ label }}</div>
        {% endfor %}
      {% endif %}
    </div>

    <div class="section-bar">JHA Development Team: We believe that all hazards have been identified and the controls listed will enable us to manage them</div>
    <table class="form-grid team-table">
      <thead>
        <tr><th>Name</th><th>Role / Position</th><th>Signature</th></tr>
      </thead>
      <tbody>
        {% for person in present_people[:6] %}
        <tr>
          <td>{{ person.participant_name or '' }}</td>
          <td>{{ person.role or '' }}</td>
          <td class="signature-cell">
            {% if person.acknowledgement_signature %}<img class="signature-image" src="{{ person.acknowledgement_signature }}">{% endif %}
          </td>
        </tr>
        {% endfor %}
        {% for i in range(6 - ([present_people|length, 6] | min)) %}
          <tr><td>&nbsp;</td><td></td><td></td></tr>
        {% endfor %}
      </tbody>
    </table>

    <table class="form-grid approval-table">
      <thead>
        <tr>
          <th colspan="3">JHA Approval</th>
          <th colspan="3">Supervisor Handover (if applicable)</th>
        </tr>
        <tr>
          <th>Name</th><th>Signature</th><th>Date / Time</th>
          <th>Name</th><th>Signature</th><th>Date / Time</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>{{ doc.reviewer_name or '' }}</td>
          <td class="signature-cell">{% if doc.review_signature %}<img class="signature-image" src="{{ doc.review_signature }}">{% endif %}</td>
          <td>{% if doc.reviewed_at %}{{ frappe.utils.format_datetime(doc.reviewed_at, 'dd-MM-yyyy HH:mm') }}{% endif %}</td>
          <td></td><td></td><td></td>
        </tr>
        <tr><td>Day Shift Supervisor:</td><td></td><td></td><td>Day Shift Supervisor:</td><td></td><td></td></tr>
        <tr><td>Night Shift Supervisor:</td><td></td><td></td><td>Night Shift Supervisor:</td><td></td><td></td></tr>
      </tbody>
    </table>

    {{ page_footer(1) }}
  </section>

  {% if doc.work_steps %}
    {% for step_batch in doc.work_steps | batch(2) %}
    <section class="pack-page matrix-page page-break-before">
      <div class="page-title compact-title">
        <div><h1>Job Hazard Analysis - Form</h1><div class="subtitle">Health and Safety</div></div>
        <div class="brand">MINE SITE SUPPORT</div>
      </div>

      <table class="matrix-table">
        <thead>
          <tr>
            <th class="step-col">Step #</th>
            <th class="task-col">TASK STEP<br><span>What am I going to do?</span></th>
            <th class="hazard-col">HAZARD<br><span>What could hurt me / others?<br>What could kill you?</span></th>
            <th class="control-col">CONTROL<br><span>What must be in place to prevent harm?<br>What are the critical controls that protect you?</span></th>
            <th class="owner-col">CRITICAL CONTROL OWNER<br><span>Who owns the Critical Control?</span></th>
            <th class="hold-col">HOLD POINT?<br><span>Sign off Name and Signature</span></th>
          </tr>
        </thead>
        <tbody>
          {% for step in step_batch %}
            {% set hazards = doc.hazards_and_controls | selectattr('work_step_sequence', 'equalto', step.sequence) | list %}
            <tr class="step-row">
              <td class="step-col">{{ step.sequence or step.idx }}</td>
              <td>{{ step.activity or '' }}</td>
              <td>
                {% if hazards|length %}
                  {% for row in hazards %}
                  <div class="hazard-block{% if not loop.first %} block-sep{% endif %}">
                    <strong>{{ row.hazard_or_energy_source or '' }}</strong>
                    {% if row.credible_consequence %}<div class="minor"><strong>Consequence:</strong> {{ row.credible_consequence }}</div>{% endif %}
                    {% if row.people_exposed %}<div class="minor"><strong>People exposed:</strong> {{ row.people_exposed }}</div>{% endif %}
                  </div>
                  {% endfor %}
                {% else %}
                  <div class="minor">No hazard/control recorded for this step.</div>
                {% endif %}
              </td>
              <td>
                {% if hazards|length %}
                  {% for row in hazards %}
                  <div class="hazard-block{% if not loop.first %} block-sep{% endif %}">
                    {% if row.existing_controls %}<div>{{ row.existing_controls }}</div>{% endif %}
                    {% if row.additional_controls %}<div class="control-extra">{{ row.additional_controls }}</div>{% endif %}
                    {% if row.critical_control %}<div class="critical-control"><strong>Critical control:</strong> {{ row.critical_control }}</div>{% endif %}
                    {% if row.verification_method %}<div class="minor"><strong>Verification:</strong> {{ row.verification_method }}</div>{% endif %}
                  </div>
                  {% endfor %}
                {% endif %}
              </td>
              <td>
                {% if hazards|length %}
                  {% for row in hazards %}
                  <div class="hazard-block{% if not loop.first %} block-sep{% endif %}">
                    {{ row.control_owner or '' }}
                    {% if row.verification_status %}<div class="minor">{{ row.verification_status }}</div>{% endif %}
                  </div>
                  {% endfor %}
                {% endif %}
              </td>
              <td>
                {% if step.hold_or_pause_point %}<strong>YES</strong>{% else %}No{% endif %}
                <div class="manual-sign-line"></div>
              </td>
            </tr>
          {% endfor %}
          {% if step_batch|length < 2 %}
            <tr class="step-row blank-step-row"><td></td><td></td><td></td><td></td><td></td><td></td></tr>
          {% endif %}
        </tbody>
      </table>

      {{ page_footer(loop.index + 1) }}
    </section>
    {% endfor %}
  {% else %}
    <section class="pack-page matrix-page page-break-before">
      <div class="page-title compact-title">
        <div><h1>Job Hazard Analysis - Form</h1><div class="subtitle">Health and Safety</div></div>
        <div class="brand">MINE SITE SUPPORT</div>
      </div>
      <table class="matrix-table">
        <thead>
          <tr>
            <th class="step-col">Step #</th>
            <th class="task-col">TASK STEP<br><span>What am I going to do?</span></th>
            <th class="hazard-col">HAZARD<br><span>What could hurt me / others?<br>What could kill you?</span></th>
            <th class="control-col">CONTROL<br><span>What must be in place to prevent harm?</span></th>
            <th class="owner-col">CRITICAL CONTROL OWNER</th>
            <th class="hold-col">HOLD POINT?</th>
          </tr>
        </thead>
        <tbody>
          <tr class="step-row blank-step-row"><td></td><td></td><td></td><td></td><td></td><td></td></tr>
          <tr class="step-row blank-step-row"><td></td><td></td><td></td><td></td><td></td><td></td></tr>
        </tbody>
      </table>
      {{ page_footer(2) }}
    </section>
  {% endif %}

  <section class="pack-page page-break-before">
    <div class="page-title compact-title">
      <div><h1>Job Hazard Analysis - Form</h1><div class="subtitle">Health and Safety</div></div>
      <div class="brand">MINE SITE SUPPORT</div>
    </div>
    <div class="section-bar centered">CHANGE MANAGEMENT AND APPROVAL</div>
    <table class="change-table">
      <thead>
        <tr><th>Date &amp; Time</th><th>Step #</th><th>Description of Change (including additional hazards)</th><th>New Controls</th><th>Change Approved<br><span>Name / Signature</span></th></tr>
      </thead>
      <tbody>
        {% for i in range(9) %}<tr><td></td><td></td><td></td><td></td><td></td></tr>{% endfor %}
      </tbody>
    </table>
    <p class="field-note">Use this page whenever the job, method, environment, plant, personnel, hazards or controls change after the JHA has been reviewed. Significant changes must also be reflected in the digital JHA revision.</p>
    {{ page_footer(matrix_pages + 2) }}
  </section>

  <section class="pack-page page-break-before sign-page">
    <div class="page-title compact-title">
      <div><h1>Job Hazard Analysis - Form</h1><div class="subtitle">Health and Safety</div></div>
      <div class="brand">MINE SITE SUPPORT</div>
    </div>
    <div class="section-bar">I have read and understood this JHA and agree with the details and risk control measures</div>
    <table class="ack-table">
      <thead><tr><th>Name</th><th>Date</th><th>Time</th><th>Signature</th><th>Name</th><th>Date</th><th>Time</th><th>Signature</th></tr></thead>
      <tbody>
        {% for person in present_people %}
        <tr>
          <td>{{ person.participant_name or '' }}</td>
          <td>{% if person.acknowledged_at %}{{ frappe.utils.formatdate(person.acknowledged_at) }}{% endif %}</td>
          <td>{% if person.acknowledged_at %}{{ frappe.utils.format_time(person.acknowledged_at) }}{% endif %}</td>
          <td class="signature-cell">{% if person.acknowledgement_signature %}<img class="signature-image" src="{{ person.acknowledgement_signature }}">{% endif %}</td>
          <td></td><td></td><td></td><td></td>
        </tr>
        {% endfor %}
        {% for i in range(13 - ([present_people|length, 13] | min)) %}<tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>{% endfor %}
      </tbody>
    </table>
    {{ page_footer(matrix_pages + 3) }}
  </section>

  <section class="pack-page page-break-before ccv-page last-page">
    <div class="page-title compact-title">
      <div><h1>Job Hazard Analysis - Form</h1><div class="subtitle">Health and Safety</div></div>
      <div class="brand">MINE SITE SUPPORT</div>
    </div>
    <h2>CCV - Field Leadership Log</h2>
    <p class="ccv-intent"><strong>JHA Task:</strong> {{ doc.work_summary_title or doc.work_summary or '' }}</p>
    <p class="ccv-intent">Use this page to record Critical Control Verifications completed against this work. If a repeat verification of the same critical risk is requested during the same shift, challenge the need and escalate in accordance with site requirements.</p>
    <table class="ccv-table">
      <thead><tr><th>Critical Risk</th><th>Date</th><th>Time</th><th>Name</th><th>Improvements Identified</th></tr></thead>
      <tbody>{% for i in range(13) %}<tr><td></td><td></td><td></td><td></td><td></td></tr>{% endfor %}</tbody>
    </table>
    {{ page_footer(matrix_pages + 4) }}
  </section>
</div>
""".strip()

PRINT_CSS = r"""
.print-format {
  orientation: Landscape;
  page-size: A4;
  margin-top: 7mm;
  margin-bottom: 9mm;
  margin-left: 9mm;
  margin-right: 9mm;
}

.jha-pack { color: #111; font-family: Arial, Helvetica, sans-serif; font-size: 7.8pt; line-height: 1.18; }
.pack-page { position: relative; box-sizing: border-box; min-height: 186mm; padding: 0 0 8mm; page-break-after: always; }
.last-page { page-break-after: auto; }
.page-break-before { page-break-before: always; }
.page-title { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 4px solid #111; padding: 0 7mm 2.5mm; margin: 0 7mm 2.5mm; }
.page-title h1 { margin: 0; font-size: 16pt; line-height: 1; font-weight: 700; }
.page-title .subtitle { margin-top: 1px; font-size: 9pt; font-weight: 700; }
.compact-title h1 { font-size: 14pt; }
.brand { font-size: 14pt; font-weight: 800; letter-spacing: .06em; white-space: nowrap; }

.form-grid, .matrix-table, .change-table, .ack-table, .ccv-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.form-grid th, .form-grid td, .matrix-table th, .matrix-table td, .change-table th, .change-table td, .ack-table th, .ack-table td, .ccv-table th, .ccv-table td { border: 1px solid #222; padding: 3px 5px; vertical-align: top; }
.form-grid th, .matrix-table thead th, .change-table thead th, .ack-table thead th, .ccv-table thead th { background: #f47a20; color: white; font-weight: 700; }

.cover-page { font-size: 7pt; }
.context-grid th { width: 13%; }
.context-grid td { width: 20%; }
.task-box { height: 13mm; font-size: 8.5pt; }
.task-box div { margin-top: 2mm; }

.critical-summary { border: 1px solid #222; padding: 3px 6px; margin-top: 1.5mm; font-size: 7.2pt; }
.check-box { display: inline-block; width: 10px; height: 10px; line-height: 9px; margin: 0 2px 0 4px; border: 1px solid #222; text-align: center; font-size: 7pt; font-weight: 700; }
.prompt-note { float: right; font-size: 6.5pt; }
.risk-strip { display: flex; flex-wrap: nowrap; gap: 2px; border: 1px solid #222; border-top: 0; min-height: 17mm; padding: 3px; }
.risk-chip { flex: 1 1 0; min-width: 0; border: 1px solid #b88700; background: #ffd34d; padding: 2px 3px; text-align: center; font-size: 5.7pt; overflow-wrap: anywhere; }
.risk-chip span { display: block; margin-top: 1px; font-size: 5.3pt; font-weight: 400; }
.empty-strip { width: 100%; text-align: center; color: #555; padding-top: 4mm; }

.section-bar { background: #f47a20; color: white; font-weight: 700; padding: 3px 6px; margin-top: 1.5mm; border: 1px solid #222; }
.centered { text-align: center; font-size: 9pt; }
.permit-grid { display: grid; grid-template-columns: repeat(4, 1fr); border-left: 1px solid #222; font-size: 6.2pt; }
.permit-item { border-right: 1px solid #222; border-bottom: 1px solid #222; min-height: 4.2mm; padding: 2px 4px; }
.team-table th { text-align: left; }
.team-table td { height: 4.5mm; }
.approval-table { margin-top: 1.5mm; }
.approval-table td { height: 5.5mm; }
.cover-page .signature-image { max-height: 5mm; }

.matrix-page { min-height: 186mm; }
.matrix-table { font-size: 7pt; }
.matrix-table thead th { text-align: center; height: 17mm; vertical-align: middle; font-size: 7.7pt; }
.matrix-table thead th span { display: block; margin-top: 2px; font-size: 6.3pt; font-weight: 400; }
.matrix-table .step-row { height: 68mm; page-break-inside: avoid; }
.matrix-table .step-row td { padding: 5px; }
.step-col { width: 7%; text-align: center; }
.task-col { width: 17%; }
.hazard-col { width: 22%; }
.control-col { width: 36%; }
.owner-col { width: 10%; }
.hold-col { width: 8%; text-align: center; }
.hazard-block { page-break-inside: avoid; }
.block-sep { border-top: 1px solid #aaa; margin-top: 4px; padding-top: 4px; }
.minor { margin-top: 2px; font-size: 6.3pt; color: #333; }
.control-extra { margin-top: 2px; }
.critical-control { margin-top: 3px; font-weight: 600; }
.manual-sign-line { height: 8mm; margin-top: 3mm; border-bottom: 1px solid #333; }
.blank-step-row td { height: 68mm; }

.change-table th:nth-child(1) { width: 10%; }
.change-table th:nth-child(2) { width: 6%; }
.change-table th:nth-child(3) { width: 40%; }
.change-table th:nth-child(4) { width: 32%; }
.change-table th:nth-child(5) { width: 12%; }
.change-table tbody td { height: 13.5mm; }
.field-note { margin-top: 2mm; font-size: 6.8pt; color: #444; }

.ack-table th:nth-child(1), .ack-table th:nth-child(5) { width: 20%; }
.ack-table th:nth-child(2), .ack-table th:nth-child(3), .ack-table th:nth-child(6), .ack-table th:nth-child(7) { width: 7%; }
.ack-table th:nth-child(4), .ack-table th:nth-child(8) { width: 16%; }
.ack-table td { height: 8.2mm; vertical-align: middle; }
.signature-cell { vertical-align: middle !important; }
.signature-image { max-height: 7mm; max-width: 34mm; object-fit: contain; }

.ccv-page h2 { color: #f47a20; font-size: 21pt; font-weight: 400; margin: 2.5mm 0 1mm; }
.ccv-intent { margin: 1mm 0; font-size: 7.5pt; }
.ccv-table { margin-top: 2.5mm; }
.ccv-table th:nth-child(1) { width: 16%; }
.ccv-table th:nth-child(2), .ccv-table th:nth-child(3) { width: 10%; }
.ccv-table th:nth-child(4) { width: 14%; }
.ccv-table th:nth-child(5) { width: 50%; }
.ccv-table tbody td { height: 8.4mm; }

.page-footer { position: absolute; bottom: 0; left: 0; right: 0; display: flex; justify-content: space-between; border-top: 1px solid #999; padding-top: 1.5mm; font-size: 5.8pt; color: #666; }

@media print {
  .step-row, .change-table tr, .ack-table tr, .ccv-table tr, .form-grid tr { page-break-inside: avoid; }
}
""".strip()


def ensure_jha_print_format() -> bool:
    if not frappe.db.exists("DocType", "Print Format") or not frappe.db.exists("DocType", JHA_DOCTYPE):
        return False

    values = {
        "doc_type": JHA_DOCTYPE,
        "custom_format": 1,
        "disabled": 0,
        "print_format_type": "Jinja",
        "html": PRINT_HTML,
        "css": PRINT_CSS,
        "font": "Default",
        "standard": "No",
    }

    if frappe.db.exists("Print Format", PRINT_FORMAT_NAME):
        doc = frappe.get_doc("Print Format", PRINT_FORMAT_NAME)
        changed = False
        for fieldname, value in values.items():
            if doc.get(fieldname) != value:
                doc.set(fieldname, value)
                changed = True
        if changed:
            doc.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Print Format",
                "name": PRINT_FORMAT_NAME,
                **values,
            }
        ).insert(ignore_permissions=True)

    frappe.clear_cache(doctype="Print Format")
    return True


def after_install():
    ensure_jha_print_format()


def after_migrate():
    ensure_jha_print_format()
