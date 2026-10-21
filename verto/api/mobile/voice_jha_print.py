from __future__ import annotations

import base64
import re
from io import BytesIO

import frappe


PRINT_FORMAT_NAME = "Digital JHA Workpack"
JHA_DOCTYPE = "Digital Job Hazard Analysis"

PRINT_FONTS = {
    "Arial": "Arial, Helvetica, sans-serif",
    "Helvetica": "Helvetica, Arial, sans-serif",
    "Verdana": "Verdana, Geneva, sans-serif",
    "Tahoma": "Tahoma, Verdana, sans-serif",
    "Trebuchet MS": "'Trebuchet MS', Arial, sans-serif",
    "Georgia": "Georgia, 'Times New Roman', serif",
    "Times New Roman": "'Times New Roman', Times, serif",
    "Courier New": "'Courier New', Courier, monospace",
}
PRINT_COLOURS = {
    "primary_colour": ("Heading Colour", "#f47a20"),
    "heading_text_colour": ("Heading Text Colour", "#ffffff"),
    "text_colour": ("Body Text Colour", "#111111"),
    "border_colour": ("Table Border Colour", "#222222"),
    "critical_risk_colour": ("Critical Risk Background Colour", "#ffd34d"),
    "critical_risk_text_colour": ("Critical Risk Text Colour", "#111111"),
    "critical_risk_border_colour": ("Critical Risk Border Colour", "#b88700"),
}
HEX_COLOUR = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\Z")
LOGO_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def validate_jha_print_settings(doc):
    """Keep user-editable branding safe to interpolate into print HTML/CSS."""
    font = doc.get("jha_print_font")
    if font and font not in PRINT_FONTS:
        frappe.throw(frappe._("Choose a font from the JHA Print Font list."))
    for key, (label, default) in PRINT_COLOURS.items():
        value = str(doc.get("jha_print_" + key) or "").strip()
        if value and not HEX_COLOUR.fullmatch(value):
            frappe.throw(frappe._("JHA Print: {0} must be a hexadecimal colour, for example #F47A20.").format(frappe._(label)))
    logo = str(doc.get("jha_print_logo") or "").strip()
    if logo and not _uploaded_logo_url(logo):
        frappe.throw(frappe._("Upload a PNG, JPEG, WebP or GIF image for the JHA Print Logo."))


def _uploaded_logo_url(value):
    return value.startswith(("/files/", "/private/files/")) and value.lower().endswith(LOGO_EXTENSIONS)


def _print_logo(value):
    """Embed an uploaded logo so private images also work in background PDFs."""
    if not _uploaded_logo_url(value):
        return ""
    from PIL import Image, ImageOps

    name = frappe.db.get_value("File", {"file_url": value}, "name")
    if not name:
        return ""
    try:
        file = frappe.get_doc("File", name)
        with Image.open(BytesIO(file.get_content())) as original:
            if original.width * original.height > 20_000_000:
                return ""
            image = ImageOps.exif_transpose(original).convert("RGBA")
            image.thumbnail((900, 300))
            output = BytesIO()
            image.save(output, format="PNG")
            return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()
    except (frappe.DoesNotExistError, OSError, Image.DecompressionBombError):
        # A removed or unreadable optional logo must not prevent a crew's print.
        return ""


def jha_print_branding():
    """Expose only print branding, including for users who cannot read settings."""
    settings = frappe.get_cached_doc("Verto Mobile Settings")
    company_name = str(settings.get("jha_print_company_name") or "").strip() or "Mine Site Support"
    branding = {
        "company_name": company_name,
        "header_text": str(settings.get("jha_print_header_text") or "").strip() or company_name.upper(),
        "font_family": PRINT_FONTS.get(settings.get("jha_print_font"), PRINT_FONTS["Arial"]),
        "logo": _print_logo(str(settings.get("jha_print_logo") or "").strip()),
    }
    for key, (label, default) in PRINT_COLOURS.items():
        value = str(settings.get("jha_print_" + key) or "").strip()
        branding[key] = value if HEX_COLOUR.fullmatch(value) else default
    return branding


def jha_workpack_qr(doc):
    import qrcode
    from frappe.utils import get_url
    from verto.api.mobile.voice_jha_fieldwork import workpack_path

    # Encode the printed revision, not an automatically changing target. The
    # authenticated destination checks its replacement chain live on each scan.
    url = get_url(workpack_path(doc))
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=5, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    output = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(output, format="PNG")
    return {"url": url, "image": "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()}


def jha_print_field_checks(doc):
    from verto.api.mobile.voice_jha_fieldwork import verification_rows
    return verification_rows(doc)


def jha_print_resources(doc):
    from verto.api.mobile.voice_jha_workpack import resource_state, evidence_file, KINDS
    from PIL import Image, ImageOps
    rows = [row for row in resource_state(doc) if row["kind"] in KINDS and not row["historical"]]
    for row in rows:
        row["thumbnail"] = None
        if row["kind"] != "Photo" or not row.get("evidence"):
            continue
        try:
            file = evidence_file(doc, row["evidence"], photo=True)
            with Image.open(BytesIO(file.get_content())) as original:
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.thumbnail((500, 300))
                output = BytesIO(); image.save(output, format="JPEG", quality=80)
                row["thumbnail"] = "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode()
        except (frappe.PermissionError, frappe.ValidationError, OSError):
            row["thumbnail"] = None
    return rows

PRINT_HTML = r"""
{% set branding = jha_print_branding() %}
<style>
.jha-pack, .jha-pack h1, .jha-pack h2 { font-family: {{ branding.font_family | safe }}; }
.jha-pack { color: {{ branding.text_colour }}; }
.jha-pack .page-title h1, .jha-pack .page-title .subtitle,
.jha-pack .page-title .brand { color: {{ branding.text_colour }}; }
.jha-pack .form-grid th, .jha-pack .matrix-table thead th,
.jha-pack .change-table thead th, .jha-pack .ack-table thead th,
.jha-pack .ccv-table thead th, .jha-pack .support-table th,
.jha-pack .section-bar { background: {{ branding.primary_colour }}; color: {{ branding.heading_text_colour }}; }
.jha-pack .ccv-page h2 { color: {{ branding.primary_colour }}; }
.jha-pack .form-grid th, .jha-pack .form-grid td,
.jha-pack .matrix-table th, .jha-pack .matrix-table td,
.jha-pack .change-table th, .jha-pack .change-table td,
.jha-pack .ack-table th, .jha-pack .ack-table td,
.jha-pack .ccv-table th, .jha-pack .ccv-table td,
.jha-pack .support-table th, .jha-pack .support-table td,
.jha-pack .critical-summary, .jha-pack .check-box,
.jha-pack .risk-strip, .jha-pack .section-bar,
.jha-pack .permit-grid, .jha-pack .permit-item { border-color: {{ branding.border_colour }}; }
.jha-pack .risk-chip { background: {{ branding.critical_risk_colour }}; color: {{ branding.critical_risk_text_colour }}; border-color: {{ branding.critical_risk_border_colour }}; }
</style>
{% set present_people = doc.participants | selectattr('present_for_discussion') | list %}
{% set critical_rows = doc.hazards_and_controls | selectattr('critical_risk') | list %}
{% set permit_rows = doc.hazards_and_controls | selectattr('permit_or_ccv_required') | list %}
{% set matrix_pages = ((doc.work_steps|length + 1) // 2) if doc.work_steps else 1 %}
{% set field_checks = jha_print_field_checks(doc) %}
{% set ccv_pages = [1, ((field_checks|length + 12) // 13)] | max %}
{% set supporting_records = jha_print_resources(doc) %}
{% set resource_pages = (supporting_records|length + 3) // 4 %}
{% set critical_extra_pages = (([critical_rows|length - 2, 0] | max) + 3) // 4 %}
{% set total_pages = matrix_pages + 3 + ccv_pages + resource_pages + critical_extra_pages %}
{% set qr = jha_workpack_qr(doc) %}

{% macro page_header(title='Job Hazard Analysis - Form', subtitle='Health and Safety') -%}
<div class="page-title">
    <div class="header-branding">
      {% if branding.logo %}<img class="brand-logo" src="{{ branding.logo | e }}" alt="{{ branding.company_name | e }} logo" />
      {% else %}<div class="brand">{{ branding.header_text | e }}</div>{% endif %}
      <a class="workpack-qr" href="{{ qr.url | e }}"><img src="{{ qr.image }}" alt="Check this JHA revision" /><span>Check current revision<br />Login required</span></a>
    </div>
    <div class="header-title"><h1>{{ title }}</h1><div class="subtitle">{{ subtitle }}</div></div>
    <div class="header-clear"></div>
</div>
{%- endmacro %}

{% macro critical_risk(row) -%}
<div class="risk-chip">
  <strong>{{ (row.hazard_or_energy_source or 'Critical Risk') | e }}</strong>
  {% if row.critical_control %}<span><strong>Critical control:</strong> {{ row.critical_control | e }}</span>{% endif %}
</div>
{%- endmacro %}

{% macro page_footer(page_no) -%}
<table class="page-footer"><tbody><tr>
  <td>THIS DOCUMENT IS UNCONTROLLED IN HARD COPY FORMAT</td>
  <td>{{ doc.name }} &nbsp; | &nbsp; Rev {{ doc.revision or 1 }} &nbsp; | &nbsp; {{ doc.jha_status }} &nbsp; | &nbsp; Page {{ page_no }} of {{ total_pages }}&nbsp;</td>
</tr></tbody></table>
{%- endmacro %}

<div class="jha-pack">
  <div class="pack-page cover-page">
    {{ page_header() }}

    <table class="form-grid context-grid">
      <tr>
        <th>Company:</th>
        <td>{{ branding.company_name | e }}</td>
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
        {% for row in critical_rows[:2] %}{{ critical_risk(row) }}{% endfor %}
        {% if critical_extra_pages %}<p class="field-note">All remaining critical risks and controls are written out on the following critical risk pages.</p>{% endif %}
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
          <th colspan="3">Team Leader Review (Supervisor or above)</th>
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
  </div>

  {% for risk_batch in critical_rows[2:] | batch(4) %}
  <div class="pack-page page-break-before">
    {{ page_header('JHA - Critical Risks and Controls') }}
    <div class="section-bar">Additional Critical Risks and Controls</div>
    <div class="risk-strip">{% for row in risk_batch %}{{ critical_risk(row) }}{% endfor %}</div>
    {{ page_footer(loop.index + 1) }}
  </div>
  {% endfor %}

  {% if doc.work_steps %}
    {% for step_batch in doc.work_steps | batch(2) %}
    <div class="pack-page matrix-page page-break-before">
      {{ page_header() }}

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

      {{ page_footer(loop.index + critical_extra_pages + 1) }}
    </div>
    {% endfor %}
  {% else %}
    <div class="pack-page matrix-page page-break-before">
      {{ page_header() }}
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
      {{ page_footer(critical_extra_pages + 2) }}
    </div>
  {% endif %}

  <div class="pack-page page-break-before">
    {{ page_header() }}
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
    {{ page_footer(matrix_pages + critical_extra_pages + 2) }}
  </div>

  <div class="pack-page page-break-before sign-page">
    {{ page_header() }}
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
    {{ page_footer(matrix_pages + critical_extra_pages + 3) }}
  </div>

  {% for ccv_page in range(ccv_pages) %}
  {% set page_checks = field_checks[ccv_page * 13:(ccv_page + 1) * 13] %}
  <div class="pack-page page-break-before ccv-page {% if loop.last and not resource_pages %}last-page{% endif %}">
    {{ page_header() }}
    <h2>CCV - Field Leadership Log</h2>
    <p class="ccv-intent"><strong>JHA Task:</strong> {{ doc.work_summary_title or doc.work_summary or '' }}</p>
    <p class="ccv-intent">Digital checks below are historical records for this revision at print time. Scan the cover QR code for live revision status. Use blank rows for field notes; manual entries are not automatically recorded digitally.</p>
    <table class="ccv-table">
      <thead><tr><th>Control / Step</th><th>Date</th><th>Time</th><th>Name</th><th>Result / CCV / Observations</th></tr></thead>
      <tbody>
        {% for check in page_checks %}<tr><td>{{ check.work_step }} · {{ check.critical_control | striptags | truncate(85, True, "…") | e }}</td><td>{{ frappe.utils.formatdate(check.verified_at) }}</td><td>{{ frappe.utils.get_datetime(check.verified_at).strftime('%H:%M') }}</td><td>{{ check.verifier_name | e }}</td><td>{{ check.result }} · {{ (check.ccv or 'No CCV linked') | e }}{% if check.notes %} · {{ check.notes | striptags | truncate(240, True, '…') | e }}{% endif %}</td></tr>{% endfor %}
        {% for i in range(13 - page_checks|length) %}<tr><td></td><td></td><td></td><td></td><td></td></tr>{% endfor %}
      </tbody>
    </table>
    {{ page_footer(matrix_pages + critical_extra_pages + 4 + ccv_page) }}
  </div>
  {% endfor %}
  {% for resource_page in range(resource_pages) %}
  <div class="pack-page page-break-before supporting-page {% if loop.last %}last-page{% endif %}">
    {{ page_header('JHA - Supporting Records', 'Permits, isolations, documents and step photos') }}
    <p class="field-note">Records and confirmations at print time for this revision. Descriptions and marker notes below are excerpts. Scan the cover QR for complete records, full-size photos and current status. A confirmed reference does not authorise work.</p>
    <table class="support-table"><thead><tr><th>Step / Reference</th><th>Record / Confirmation</th><th>Photo / Evidence</th></tr></thead><tbody>
    {% for item in supporting_records[resource_page * 4:(resource_page + 1) * 4] %}
      <tr><td><strong>Step {{ item.work_step }}</strong><br />{{ item.step_activity | striptags | truncate(80, True, '...') | e }}<br /><strong>{{ item.kind | e }}: {{ (item.reference or item.ehs_permit or item.name) | e }}</strong></td>
      <td><strong>{{ item.effective_status | e }}</strong>{% if item.expires_at %} - Expires {{ item.expires_at | e }}{% endif %}<br />{{ item.details | striptags | truncate(200, True, '...') | e }}
        {% for point in item.annotations[:3] %}<div>{{ loop.index }}. {{ point.label | striptags | truncate(90, True, '...') | e }}</div>{% endfor %}
        {% if item.annotations|length > 3 %}<div>{{ item.annotations|length - 3 }} more marker notes in the digital record.</div>{% endif %}
        <div class="minor">{{ item.recorder_name | e }} - {{ item.recorded_at | e }}</div></td>
      <td>{% if item.thumbnail %}<div class="support-photo"><img src="{{ item.thumbnail }}" alt="Step supporting photo" />{% for point in item.annotations %}<span style="left:{{ point.x * 100 }}%;top:{{ point.y * 100 }}%;">{{ loop.index }}</span>{% endfor %}</div>{% elif item.evidence %}Supporting file attached. Open through the digital JHA.{% else %}No readable supporting file attached.{% endif %}</td></tr>
    {% endfor %}
    </tbody></table>
    {{ page_footer(matrix_pages + critical_extra_pages + 4 + ccv_pages + resource_page) }}
  </div>
  {% endfor %}
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
.workpack-qr { display: block; width: 19mm; margin: 1mm 0 0 auto; color: #111; text-align: center; font-size: 4.5pt; line-height: 1.05; text-decoration: none; }
.print-format .workpack-qr img { display: block; width: 16mm !important; height: 16mm; margin: 0 auto; }
.pack-page { display: block; box-sizing: border-box; page-break-after: always; }
.last-page { page-break-after: auto; }
.page-title { width: 100%; border-bottom: 4px solid #111; padding-bottom: 2mm; margin: 0 0 2mm; page-break-inside: avoid; }
.header-branding { float: right; width: 60mm; text-align: right; }
.header-title { margin-right: 62mm; }
.header-clear { clear: both; }
.page-title h1 { margin: 0; font-size: 16pt; line-height: 1; font-weight: 700; }
.page-title .subtitle { margin-top: 1px; font-size: 9pt; font-weight: 700; }
.brand { font-size: 14pt; font-weight: 800; letter-spacing: .06em; overflow-wrap: break-word; }
.print-format .brand-logo { display: block; width: auto !important; max-width: 50mm; max-height: 8mm; margin: 0 0 1mm auto; }

.form-grid, .matrix-table, .change-table, .ack-table, .ccv-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.form-grid th, .form-grid td, .matrix-table th, .matrix-table td, .change-table th, .change-table td, .ack-table th, .ack-table td, .ccv-table th, .ccv-table td { box-sizing: border-box; border: 1px solid #222; padding: 3px 5px; vertical-align: top; }
.form-grid th, .matrix-table thead th, .change-table thead th, .ack-table thead th, .ccv-table thead th { background: #f47a20; color: white; font-weight: 700; }

.cover-page { font-size: 7pt; }
.context-grid th { width: 13%; }
.context-grid td { width: 20%; }
.task-box { height: 13mm; font-size: 8.5pt; }
.task-box div { margin-top: 2mm; }

.critical-summary { border: 1px solid #222; padding: 3px 6px; margin-top: 1.5mm; font-size: 7.2pt; }
.check-box { display: inline-block; width: 10px; height: 10px; line-height: 9px; margin: 0 2px 0 4px; border: 1px solid #222; text-align: center; font-size: 7pt; font-weight: 700; }
.prompt-note { float: right; font-size: 6.5pt; }
.risk-strip { border: 1px solid #222; border-top: 0; padding: 1mm; }
.risk-chip { border: 1px solid #b88700; background: #ffd34d; padding: 1mm 1.5mm; margin-bottom: 1mm; text-align: left; font-size: 7pt; overflow-wrap: break-word; word-wrap: break-word; page-break-inside: avoid; }
.risk-chip:last-child { margin-bottom: 0; }
.risk-chip span { display: block; margin-top: 1mm; font-size: 6.8pt; font-weight: 400; white-space: pre-line; }
.empty-strip { width: 100%; text-align: center; color: #555; padding-top: 4mm; }

.section-bar { background: #f47a20; color: white; font-weight: 700; padding: 3px 6px; margin-top: 1.5mm; border: 1px solid #222; }
.centered { text-align: center; font-size: 9pt; }
.permit-grid { border-left: 1px solid #222; font-size: 0; }
.permit-item { display: inline-block; box-sizing: border-box; width: 25%; vertical-align: top; font-size: 6.2pt; border-right: 1px solid #222; border-bottom: 1px solid #222; min-height: 4.2mm; padding: 2px 4px; }
.team-table th { text-align: left; }
.team-table td { height: 4.5mm; }
.approval-table { margin-top: 1.5mm; }
.approval-table td { height: 5.5mm; }
.cover-page .signature-image { max-height: 5mm; }

.matrix-page { min-height: 0; }
.matrix-table { font-size: 7pt; }
.matrix-table thead th { text-align: center; height: 17mm; vertical-align: middle; font-size: 7.7pt; }
.matrix-table thead th span { display: block; margin-top: 2px; font-size: 6.3pt; font-weight: 400; }
.matrix-table .step-row { height: 64mm; page-break-inside: avoid; }
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
.blank-step-row td { height: 64mm; }

.change-table th:nth-child(1) { width: 10%; }
.change-table th:nth-child(2) { width: 6%; }
.change-table th:nth-child(3) { width: 40%; }
.change-table th:nth-child(4) { width: 32%; }
.change-table th:nth-child(5) { width: 12%; }
.change-table tbody td { height: 12mm; }
.field-note { margin-top: 2mm; font-size: 6.8pt; color: #444; }

.ack-table th:nth-child(1), .ack-table th:nth-child(5) { width: 20%; }
.ack-table th:nth-child(2), .ack-table th:nth-child(3), .ack-table th:nth-child(6), .ack-table th:nth-child(7) { width: 7%; }
.ack-table th:nth-child(4), .ack-table th:nth-child(8) { width: 16%; }
.ack-table td { height: 7mm; vertical-align: middle; }
.signature-cell { vertical-align: middle !important; }
.signature-image { max-height: 7mm; max-width: 34mm; object-fit: contain; }

.ccv-page h2 { color: #f47a20; font-size: 21pt; font-weight: 400; margin: 2.5mm 0 1mm; }
.ccv-intent { margin: 1mm 0; font-size: 7.5pt; }
.ccv-table { margin-top: 2.5mm; }
.ccv-table th:nth-child(1) { width: 16%; }
.ccv-table th:nth-child(2), .ccv-table th:nth-child(3) { width: 10%; }
.ccv-table th:nth-child(4) { width: 14%; }
.ccv-table th:nth-child(5) { width: 50%; }
.ccv-table tbody td { height: 7mm; }
.ccv-table td { overflow-wrap: anywhere; }
.support-table { width: 100%; table-layout: fixed; border-collapse: collapse; margin-top: 3mm; font-size: 7pt; }
.support-table th, .support-table td { box-sizing: border-box; border: 1px solid #222; padding: 2mm; vertical-align: top; overflow-wrap: anywhere; }
.support-table th { background: #f47a20; color: white; }
.support-table th:nth-child(1) { width: 24%; }
.support-table th:nth-child(2) { width: 52%; }
.support-table th:nth-child(3) { width: 24%; }
.support-table tbody tr { height: 34mm; page-break-inside: avoid; }
.support-photo { position: relative; display: inline-block; }
.support-photo img { display: block; max-height: 27mm; max-width: 55mm; }
.support-photo span { position: absolute; transform: translate(-50%, -50%); border: 1px solid white; border-radius: 50%; background: #c00; color: white; width: 3.5mm; height: 3.5mm; text-align: center; line-height: 3.5mm; font-size: 6pt; }

.page-footer { width: 100%; table-layout: fixed; border-collapse: collapse; border-top: 1px solid #999; margin-top: 3mm; font-size: 5.8pt; color: #666; }
.print-format .page-footer td { border: 0; padding: 1.5mm 0 0; color: #666; }
.page-footer td:first-child { width: 45%; }
.page-footer td:last-child { text-align: right; padding-right: 1.5mm; }

@media print {
  .print-format { margin: 0 !important; padding: 0 !important; max-width: none; min-height: 0; }
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
