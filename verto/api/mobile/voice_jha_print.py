from __future__ import annotations

import frappe


PRINT_FORMAT_NAME = "Digital JHA Workpack"
JHA_DOCTYPE = "Digital Job Hazard Analysis"

PRINT_HTML = r'''
<div class='jha-workpack'>
  <div class='jha-header'>
    <div>
      <div class='jha-kicker'>MINE SITE SUPPORT</div>
      <h1>JOB HAZARD ANALYSIS</h1>
      <div class='jha-subtitle'>Workpack Review Copy</div>
    </div>
    <div class='jha-meta'>
      <div><strong>JHA:</strong> {{ doc.name }}</div>
      <div><strong>Revision:</strong> {{ doc.revision or 1 }}</div>
      <div><strong>Status:</strong> {{ doc.jha_status }}</div>
    </div>
  </div>

  <div class='jha-notice'>
    This document records hazards and controls discussed for the work described below.
    It does not by itself authorise work to proceed. Required permits, isolations, approvals
    and site controls remain mandatory. If the work scope, steps, personnel or conditions change,
    pause and reassess the JHA before continuing.
  </div>

  <h3>Work Context</h3>
  <table class='context-table'>
    <tbody>
      <tr>
        <th>Project</th>
        <td>{{ doc.project or '' }}</td>
        <th>Work Order</th>
        <td>{{ doc.work_order_number or '' }}</td>
      </tr>
      <tr>
        <th>Work Summary</th>
        <td colspan='3'>{{ doc.work_summary_title or doc.work_summary or '' }}</td>
      </tr>
      <tr>
        <th>Work Area</th>
        <td>{{ doc.work_area or '' }}</td>
        <th>Prepared</th>
        <td>{{ frappe.utils.format_datetime(doc.creation, 'dd-MM-yyyy HH:mm') if doc.creation else '' }}</td>
      </tr>
    </tbody>
  </table>

  <h3>Planned Work Steps</h3>
  <table class='jha-table work-steps'>
    <thead>
      <tr>
        <th class='col-step'>Step</th>
        <th>Activity</th>
        <th class='col-hold'>Hold / Pause Point</th>
      </tr>
    </thead>
    <tbody>
      {% for step in doc.work_steps %}
      <tr>
        <td>{{ step.sequence or loop.index }}</td>
        <td>{{ step.activity or '' }}</td>
        <td>{{ 'Yes' if step.hold_or_pause_point else 'No' }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <h3>Hazards and Controls</h3>
  <table class='jha-table hazards'>
    <thead>
      <tr>
        <th class='col-step'>Step</th>
        <th>Hazard / Energy</th>
        <th>Credible Consequence</th>
        <th>Controls</th>
        <th>Owner / Verification</th>
        <th class='col-risk'>Residual Risk</th>
      </tr>
    </thead>
    <tbody>
      {% for row in doc.hazards_and_controls %}
      <tr>
        <td>{{ row.work_step_sequence or '' }}</td>
        <td>
          <strong>{{ row.hazard_or_energy_source or '' }}</strong>
          {% if row.people_exposed %}
          <div class='small'><strong>Exposed:</strong> {{ row.people_exposed }}</div>
          {% endif %}
        </td>
        <td>{{ row.credible_consequence or '' }}</td>
        <td>
          {% if row.existing_controls %}<div><strong>Existing:</strong> {{ row.existing_controls }}</div>{% endif %}
          {% if row.additional_controls %}<div><strong>Additional:</strong> {{ row.additional_controls }}</div>{% endif %}
          {% if row.hierarchy_level %}<div class='small'><strong>Hierarchy:</strong> {{ row.hierarchy_level }}</div>{% endif %}
          {% if row.critical_risk %}<div class='critical'><strong>Critical Risk:</strong> {{ row.critical_control or 'Critical control to be confirmed' }}</div>{% endif %}
          {% if row.permit_or_ccv_required %}<div class='small'><strong>Permit / CCV:</strong> {{ row.permit_or_ccv_required }}</div>{% endif %}
        </td>
        <td>
          {% if row.control_owner %}<div><strong>Owner:</strong> {{ row.control_owner }}</div>{% endif %}
          {% if row.verification_method %}<div><strong>Verify:</strong> {{ row.verification_method }}</div>{% endif %}
          {% if row.verification_status %}<div class='small'>{{ row.verification_status }}</div>{% endif %}
        </td>
        <td>{{ row.residual_risk or '' }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <div class='page-break-avoid'>
    <h3>Human Review</h3>
    <p class='declaration'>
      I have reviewed this JHA against the planned work and the crew discussion.
      I understand that signing this review does not itself authorise work to proceed.
    </p>

    <table class='sign-table'>
      <tbody>
        <tr>
          <th>Reviewer Name</th>
          <td>
            {% if doc.review_completed %}
              {{ doc.reviewer_name or doc.reviewed_by or '' }}
            {% else %}
              <span class='write-line'></span>
            {% endif %}
          </td>
          <th>Date / Time</th>
          <td>
            {% if doc.reviewed_at %}
              {{ frappe.utils.format_datetime(doc.reviewed_at, 'dd-MM-yyyy HH:mm') }}
            {% else %}
              <span class='write-line'></span>
            {% endif %}
          </td>
        </tr>
        <tr>
          <th>Reviewer Signature</th>
          <td colspan='3' class='signature-cell'>
            {% if doc.review_signature %}
              <img class='signature-image' src='{{ doc.review_signature }}' alt='Reviewer signature'>
            {% else %}
              <span class='signature-line'></span>
            {% endif %}
          </td>
        </tr>
        {% if doc.review_notes %}
        <tr>
          <th>Review Notes</th>
          <td colspan='3'>{{ doc.review_notes }}</td>
        </tr>
        {% endif %}
      </tbody>
    </table>
  </div>

  <div class='page-break-avoid'>
    <h3>Personnel Acknowledgement</h3>
    <p class='declaration'>
      By signing below, each person confirms they have reviewed this JHA, understand the hazards
      and controls discussed, and will raise any change or uncertainty before proceeding.
    </p>

    <table class='jha-table participant-table'>
      <thead>
        <tr>
          <th>Participant</th>
          <th>Role</th>
          <th class='participant-sign'>Signature</th>
          <th class='participant-date'>Date / Time</th>
        </tr>
      </thead>
      <tbody>
        {% for person in doc.participants %}
          {% if person.present_for_discussion %}
          <tr>
            <td>{{ person.participant_name or '' }}</td>
            <td>{{ person.role or '' }}</td>
            <td class='signature-cell'>
              {% if person.acknowledgement_signature %}
                <img class='signature-image' src='{{ person.acknowledgement_signature }}' alt='Participant signature'>
              {% else %}
                <span class='signature-line'></span>
              {% endif %}
            </td>
            <td>
              {% if person.acknowledged_at %}
                {{ frappe.utils.format_datetime(person.acknowledged_at, 'dd-MM-yyyy HH:mm') }}
              {% else %}
                <span class='write-line'></span>
              {% endif %}
            </td>
          </tr>
          {% endif %}
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class='paper-control'>
    <strong>Paper copy control:</strong>
    Manual signatures on this printed copy are physical acknowledgements and are not automatically
    recorded in ERPNext. Retain the signed copy with the workpack in accordance with site document-control requirements.
    Digital JHA reference: {{ doc.name }} · Revision {{ doc.revision or 1 }}.
  </div>
</div>
'''.strip()

PRINT_CSS = r'''
.jha-workpack { font-size: 9.5pt; color: #111827; line-height: 1.35; }
.jha-header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #111827; padding-bottom: 8px; margin-bottom: 10px; }
.jha-kicker { font-size: 8pt; font-weight: 700; letter-spacing: .08em; color: #4b5563; }
.jha-header h1 { font-size: 20pt; margin: 1px 0 0; letter-spacing: .02em; }
.jha-subtitle { font-size: 9pt; color: #6b7280; margin-top: 2px; }
.jha-meta { min-width: 180px; border: 1px solid #9ca3af; padding: 6px 8px; font-size: 8.5pt; }
.jha-notice { border: 1px solid #d1d5db; background: #f9fafb; padding: 7px 9px; margin: 8px 0 12px; font-size: 8.5pt; }
.jha-workpack h3 { font-size: 11pt; margin: 12px 0 5px; border-bottom: 1px solid #9ca3af; padding-bottom: 2px; }
.context-table, .jha-table, .sign-table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
.context-table th, .context-table td, .jha-table th, .jha-table td, .sign-table th, .sign-table td { border: 1px solid #9ca3af; padding: 5px 6px; vertical-align: top; }
.context-table th, .sign-table th { width: 16%; background: #f3f4f6; font-weight: 700; }
.jha-table thead th { background: #e5e7eb; font-weight: 700; text-align: left; }
.jha-table .col-step { width: 6%; text-align: center; }
.jha-table .col-hold { width: 16%; }
.jha-table .col-risk { width: 10%; }
.hazards { font-size: 8.3pt; }
.small { font-size: 7.7pt; margin-top: 2px; color: #374151; }
.critical { margin-top: 3px; padding: 2px 3px; border: 1px solid #b91c1c; font-size: 7.7pt; }
.declaration { margin: 4px 0 7px; font-size: 8.5pt; }
.signature-cell { height: 42px; vertical-align: middle !important; }
.signature-image { max-height: 38px; max-width: 180px; object-fit: contain; }
.signature-line, .write-line { display: block; min-height: 24px; border-bottom: 1px solid #111827; }
.participant-sign { width: 28%; }
.participant-date { width: 17%; }
.participant-table td { height: 42px; vertical-align: middle; }
.paper-control { margin-top: 12px; border-top: 1px solid #9ca3af; padding-top: 6px; font-size: 7.5pt; color: #4b5563; }
.page-break-avoid { page-break-inside: avoid; }
@media print { .jha-table tr, .context-table tr, .sign-table tr { page-break-inside: avoid; } }
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
