from __future__ import annotations

import frappe


PRINT_FORMAT_NAME = "Digital JHA Workpack"
JHA_DOCTYPE = "Digital Job Hazard Analysis"

PRINT_HTML = r'''
<div class="jha-pack">
  <div class="doc-footer">
    <span>THIS DOCUMENT IS UNCONTROLLED IN HARD COPY FORMAT</span>
    <span>{{ doc.name }} &nbsp; | &nbsp; Rev {{ doc.revision or 1 }} &nbsp; | &nbsp; {{ doc.jha_status }}</span>
  </div>

  <section class="pack-page cover-page">
    <div class="page-title">
      <div>
        <h1>Job Hazard Analysis – Form</h1>
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

    {% set critical_rows = doc.hazards_and_controls | selectattr('critical_risk') | list %}
    <div class="critical-summary">
      <strong>Critical Risk Management:</strong>
      Is a critical risk involved in this task?
      <span class="check-box">{% if critical_rows|length %}X{% endif %}</span> Yes
      <span class="check-box">{% if not critical_rows|length %}X{% endif %}</span> No
      <span class="prompt-note">If yes, review the applicable critical controls before work starts.</span>
    </div>

    <div class="risk-strip">
      {% if critical_rows|length %}
        {% for row in critical_rows %}
          <div class="risk-chip">
            <strong>{{ row.hazard_or_energy_source or 'Critical Risk' }}</strong>
            {% if row.critical_control %}<span>{{ row.critical_control }}</span>{% endif %}
          </div>
        {% endfor %}
      {% else %}
        <div class="empty-strip">No critical risks have been marked in the digital JHA.</div>
      {% endif %}
    </div>

    <div class="section-bar">Additional Permits / Clearances</div>
    <div class="permit-grid">
      {% set permit_rows = doc.hazards_and_controls | selectattr('permit_or_ccv_required') | list %}
      {% if permit_rows|length %}
        {% for row in permit_rows %}
          <div class="permit-item"><span class="check-box">X</span>{{ row.permit_or_ccv_required }}</div>
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
        {% for person in doc.participants %}
          {% if person.present_for_discussion %}
          <tr>
            <td>{{ person.participant_name or '' }}</td>
            <td>{{ person.role or '' }}</td>
            <td class="signature-cell">
              {% if person.acknowledgement_signature %}<img class="signature-image" src="{{ person.acknowledgement_signature }}">{% endif %}
            </td>
          </tr>
          {% endif %}
        {% endfor %}
        {% if not doc.participants %}
          {% for i in range(4) %}<tr><td>&nbsp;</td><td></td><td></td></tr>{% endfor %}
        {% endif %}
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
  </section>

  <section class="pack-page task-page page-break-before">
    <div class="page-title compact-title">
      <div><h1>Job Hazard Analysis – Form</h1><div class="subtitle">Health and Safety</div></div>
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
        {% for step in doc.work_steps %}
          {% set hazards = doc.hazards_and_controls | selectattr('work_step_sequence', 'equalto', step.sequence) | list %}
          {% if hazards|length %}
            {% for row in hazards %}
            <tr>
              <td class="step-col">{{ step.sequence or step.idx }}</td>
              <td>{{ step.activity or '' }}</td>
              <td>
                <strong>{{ row.hazard_or_energy_source or '' }}</strong>
                {% if row.credible_consequence %}<div class="minor"><strong>Consequence:</strong> {{ row.credible_consequence }}</div>{% endif %}
                {% if row.people_exposed %}<div class="minor"><strong>People exposed:</strong> {{ row.people_exposed }}</div>{% endif %}
              </td>
              <td>
                {% if row.existing_controls %}<div>{{ row.existing_controls }}</div>{% endif %}
                {% if row.additional_controls %}<div class="control-extra">{{ row.additional_controls }}</div>{% endif %}
                {% if row.critical_control %}<div class="critical-control"><strong>Critical control:</strong> {{ row.critical_control }}</div>{% endif %}
                {% if row.verification_method %}<div class="minor"><strong>Verification:</strong> {{ row.verification_method }}</div>{% endif %}
              </td>
              <td>
                {{ row.control_owner or '' }}
                {% if row.verification_status %}<div class="minor">{{ row.verification_status }}</div>{% endif %}
              </td>
              <td>
                {% if step.hold_or_pause_point %}<strong>YES</strong>{% else %}No{% endif %}
                <div class="manual-sign-line"></div>
              </td>
            </tr>
            {% endfor %}
          {% else %}
            <tr>
              <td>{{ step.sequence or step.idx }}</td>
              <td>{{ step.activity or '' }}</td>
              <td></td><td></td><td></td>
              <td>{% if step.hold_or_pause_point %}<strong>YES</strong>{% else %}No{% endif %}<div class="manual-sign-line"></div></td>
            </tr>
          {% endif %}
        {% endfor %}
        {% if not doc.work_steps %}
          {% for i in range(8) %}<tr class="blank-matrix-row"><td></td><td></td><td></td><td></td><td></td><td></td></tr>{% endfor %}
        {% endif %}
      </tbody>
    </table>
  </section>

  <section class="pack-page page-break-before">
    <div class="page-title compact-title">
      <div><h1>Job Hazard Analysis – Form</h1><div class="subtitle">Health and Safety</div></div>
      <div class="brand">MINE SITE SUPPORT</div>
    </div>
    <div class="section-bar centered">CHANGE MANAGEMENT AND APPROVAL</div>
    <table class="change-table">
      <thead>
        <tr><th>Date &amp; Time</th><th>Step #</th><th>Description of Change (including additional hazards)</th><th>New Controls</th><th>Change Approved<br><span>Name / Signature</span></th></tr>
      </thead>
      <tbody>
        {% for i in range(10) %}<tr><td></td><td></td><td></td><td></td><td></td></tr>{% endfor %}
      </tbody>
    </table>
    <p class="field-note">Use this page whenever the job, method, environment, plant, personnel, hazards or controls change after the JHA has been reviewed. Significant changes must also be reflected in the digital JHA revision.</p>
  </section>

  <section class="pack-page page-break-before sign-page">
    <div class="page-title compact-title">
      <div><h1>Job Hazard Analysis – Form</h1><div class="subtitle">Health and Safety</div></div>
      <div class="brand">MINE SITE SUPPORT</div>
    </div>
    <div class="section-bar">I have read and understood this JHA and agree with the details and risk control measures</div>
    <table class="ack-table">
      <thead><tr><th>Name</th><th>Date</th><th>Time</th><th>Signature</th><th>Name</th><th>Date</th><th>Time</th><th>Signature</th></tr></thead>
      <tbody>
        {% for person in doc.participants %}
          {% if person.present_for_discussion %}
          <tr>
            <td>{{ person.participant_name or '' }}</td>
            <td>{% if person.acknowledged_at %}{{ frappe.utils.formatdate(person.acknowledged_at) }}{% endif %}</td>
            <td>{% if person.acknowledged_at %}{{ frappe.utils.format_time(person.acknowledged_at) }}{% endif %}</td>
            <td class="signature-cell">{% if person.acknowledgement_signature %}<img class="signature-image" src="{{ person.acknowledgement_signature }}">{% endif %}</td>
            <td></td><td></td><td></td><td></td>
          </tr>
          {% endif %}
        {% endfor %}
        {% for i in range(12) %}<tr><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>{% endfor %}
      </tbody>
    </table>
  </section>

  <section class="pack-page page-break-before ccv-page">
    <div class="page-title compact-title">
      <div><h1>Job Hazard Analysis – Form</h1><div class="subtitle">Health and Safety</div></div>
      <div class="brand">MINE SITE SUPPORT</div>
    </div>
    <h2>CCV – Field Leadership Log</h2>
    <p class="ccv-intent"><strong>JHA Task:</strong> {{ doc.work_summary_title or doc.work_summary or '' }}</p>
    <p class="ccv-intent">Use this page to record Critical Control Verifications completed against this work. If a repeat verification of the same critical risk is requested during the same shift, challenge the need and escalate in accordance with site requirements.</p>
    <table class="ccv-table">
      <thead><tr><th>Critical Risk</th><th>Date</th><th>Time</th><th>Name</th><th>Improvements Identified</th></tr></thead>
      <tbody>{% for i in range(14) %}<tr><td></td><td></td><td></td><td></td><td></td></tr>{% endfor %}</tbody>
    </table>
  </section>
</div>
'''.strip()

PRINT_CSS = r'''
@page { size: A4 landscape; margin: 9mm 9mm 13mm 9mm; }

.jha-pack { color: #111; font-family: Arial, Helvetica, sans-serif; font-size: 8.5pt; line-height: 1.25; }
.pack-page { position: relative; min-height: 174mm; }
.page-break-before { page-break-before: always; }
.page-title { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 4px solid #111; padding: 0 8mm 3mm; margin: 0 8mm 3mm; }
.page-title h1 { margin: 0; font-size: 18pt; line-height: 1; font-weight: 700; }
.page-title .subtitle { margin-top: 2px; font-size: 10pt; font-weight: 700; }
.compact-title h1 { font-size: 15pt; }
.brand { font-size: 15pt; font-weight: 800; letter-spacing: .06em; white-space: nowrap; }

.form-grid, .matrix-table, .change-table, .ack-table, .ccv-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.form-grid th, .form-grid td, .matrix-table th, .matrix-table td, .change-table th, .change-table td, .ack-table th, .ack-table td, .ccv-table th, .ccv-table td { border: 1px solid #222; padding: 4px 6px; vertical-align: top; }
.form-grid th, .matrix-table thead th, .change-table thead th, .ack-table thead th, .ccv-table thead th { background: #f47a20; color: white; font-weight: 700; }
.context-grid th { width: 13%; }
.context-grid td { width: 20%; min-height: 8mm; }
.task-box { height: 22mm; font-size: 10pt; }
.task-box div { margin-top: 3mm; }

.critical-summary { border: 1px solid #222; padding: 5px 8px; margin-top: 2mm; font-size: 8.5pt; }
.check-box { display: inline-block; width: 11px; height: 11px; line-height: 10px; margin: 0 2px 0 5px; border: 1px solid #222; text-align: center; font-size: 8pt; font-weight: 700; }
.prompt-note { float: right; font-size: 7.5pt; }
.risk-strip { display: flex; flex-wrap: wrap; gap: 3px; border: 1px solid #222; border-top: 0; min-height: 14mm; padding: 4px; }
.risk-chip { flex: 1 1 14%; min-width: 24mm; border: 1px solid #b88700; background: #ffd34d; padding: 3px 4px; text-align: center; font-size: 7pt; }
.risk-chip span { display: block; margin-top: 2px; font-weight: 400; }
.empty-strip { width: 100%; text-align: center; color: #555; padding-top: 4mm; }

.section-bar { background: #f47a20; color: white; font-weight: 700; padding: 4px 7px; margin-top: 2mm; border: 1px solid #222; }
.centered { text-align: center; font-size: 10pt; }
.permit-grid { display: grid; grid-template-columns: repeat(4, 1fr); border-left: 1px solid #222; }
.permit-item { border-right: 1px solid #222; border-bottom: 1px solid #222; min-height: 6mm; padding: 3px 5px; }
.team-table th { text-align: left; }
.team-table td { height: 7mm; }
.approval-table { margin-top: 2mm; }
.approval-table td { height: 8mm; }

.matrix-table { font-size: 7.8pt; }
.matrix-table thead { display: table-header-group; }
.matrix-table thead th { text-align: center; height: 20mm; vertical-align: middle; font-size: 8.5pt; }
.matrix-table thead th span { display: block; margin-top: 3px; font-size: 7.2pt; font-weight: 400; }
.matrix-table tbody tr { page-break-inside: avoid; min-height: 22mm; }
.matrix-table tbody td { min-height: 22mm; padding: 5px; }
.step-col { width: 7%; text-align: center; }
.task-col { width: 18%; }
.hazard-col { width: 20%; }
.control-col { width: 38%; }
.owner-col { width: 9%; }
.hold-col { width: 8%; text-align: center; }
.minor { margin-top: 3px; font-size: 6.9pt; color: #333; }
.control-extra { margin-top: 3px; }
.critical-control { margin-top: 4px; font-weight: 600; }
.manual-sign-line { height: 9mm; margin-top: 3mm; border-bottom: 1px solid #333; }
.blank-matrix-row td { height: 18mm; }

.change-table thead { display: table-header-group; }
.change-table th:nth-child(1) { width: 10%; }
.change-table th:nth-child(2) { width: 6%; }
.change-table th:nth-child(3) { width: 40%; }
.change-table th:nth-child(4) { width: 32%; }
.change-table th:nth-child(5) { width: 12%; }
.change-table tbody td { height: 14mm; }
.field-note { margin-top: 3mm; font-size: 7.5pt; color: #444; }

.ack-table thead { display: table-header-group; }
.ack-table th:nth-child(1), .ack-table th:nth-child(5) { width: 20%; }
.ack-table th:nth-child(2), .ack-table th:nth-child(3), .ack-table th:nth-child(6), .ack-table th:nth-child(7) { width: 7%; }
.ack-table th:nth-child(4), .ack-table th:nth-child(8) { width: 16%; }
.ack-table td { height: 9mm; vertical-align: middle; }
.signature-cell { vertical-align: middle !important; }
.signature-image { max-height: 8mm; max-width: 36mm; object-fit: contain; }

.ccv-page h2 { color: #f47a20; font-size: 22pt; font-weight: 400; margin: 3mm 0 1mm; }
.ccv-intent { margin: 1mm 0; font-size: 8pt; }
.ccv-table { margin-top: 3mm; }
.ccv-table th:nth-child(1) { width: 16%; }
.ccv-table th:nth-child(2), .ccv-table th:nth-child(3) { width: 10%; }
.ccv-table th:nth-child(4) { width: 14%; }
.ccv-table th:nth-child(5) { width: 50%; }
.ccv-table tbody td { height: 9mm; }

.doc-footer { position: fixed; bottom: -9mm; left: 0; right: 0; display: flex; justify-content: space-between; border-top: 1px solid #999; padding-top: 2mm; font-size: 6.2pt; color: #666; }

@media print {
  .matrix-table tr, .change-table tr, .ack-table tr, .ccv-table tr, .form-grid tr { page-break-inside: avoid; }
}
'''.strip()


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
