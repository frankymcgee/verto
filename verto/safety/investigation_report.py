"""Self-contained investigation PDF with vector maps and original evidence files.

No URL fetching or shell/Office execution is used. The API supplies only files
whose investigation and File permissions have already been checked.
"""

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

from PIL import Image as PILImage, ImageOps, ImageSequence
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate

from verto.safety.investigation_rules import ICAM_CATEGORIES, checked, text
from verto.safety.investigation_workflow import diagram, event_type, ordered_timeline

MAX_BYTES = 100 * 1024 * 1024
MAX_PAGES = 1000
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff", ".bmp"}


class ReportLimitError(ValueError):
    pass


def _styles():
    font, bold = "Helvetica", "Helvetica-Bold"
    regular_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if regular_path.exists():
        font, bold = "VertoReport", "VertoReportBold"
        if font not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font, str(regular_path)))
            pdfmetrics.registerFont(TTFont(bold, str(regular_path.with_name("DejaVuSans-Bold.ttf"))))
            pdfmetrics.registerFontFamily(font, normal=font, bold=bold)
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = font
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 14
    styles["BodyText"].spaceAfter = 7
    styles["BodyText"].splitLongWords = True
    styles["Heading1"].fontName = bold
    styles["Heading1"].fontSize = 21
    styles["Heading1"].leading = 27
    styles["Heading1"].textColor = colors.HexColor("#18354a")
    styles["Heading2"].fontName = bold
    styles["Heading2"].fontSize = 14
    styles["Heading2"].leading = 19
    styles["Heading2"].spaceBefore = 17
    styles["Heading2"].textColor = colors.HexColor("#18354a")
    styles["Heading3"].fontName = bold
    styles["Heading3"].fontSize = 10
    styles["Heading3"].leading = 15
    styles.add(ParagraphStyle("SmallNote", parent=styles["BodyText"], fontSize=8, leading=11, textColor=colors.HexColor("#526478")))
    return styles


def _paragraph(value, style):
    # Findings and uploaded document text are always text, never report markup.
    return Paragraph(escape(text(value) or "Not recorded").replace("\n", "<br/>"), style)


def _render(story, styles, title):
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=42, rightMargin=42,
        topMargin=42, bottomMargin=42, title=title, author="Verto Investigations")

    def footer(c, doc):
        c.setFont(styles["SmallNote"].fontName, 7)
        c.setFillColor(colors.HexColor("#64748b"))
        c.drawString(42, 23, "VERTO  |  CONFIDENTIAL INVESTIGATION REPORT")

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def _details(doc, styles, overview=False):
    story = []

    def p(value, style="BodyText"):
        story.append(_paragraph(value, styles[style]))

    def field(label, value):
        story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(text(value) or 'Not recorded').replace(chr(10), '<br/>')}", styles["BodyText"]))

    if overview:
        p("VERTO / INVESTIGATION REPORT / CONFIDENTIAL", "SmallNote")
        p(doc.get("title"), "Heading1")
        p(" | ".join(text(doc.get(key)) for key in ("name", "method", "status")), "Heading3")
        for key, label in (("incident_datetime", "Incident date/time"), ("incident_time_precision", "Time precision"),
            ("project", "Project"), ("site_location", "Site / area"), ("incident_type", "Incident type"),
            ("classification", "Classification"), ("actual_severity", "Actual consequence"),
            ("potential_severity", "Potential consequence"), ("external_reference", "External reference"),
            ("due_date", "Investigation due"), ("modified", "Saved revision")):
            field(label, doc.get(key))
        field("Source incident", " / ".join(text(doc.get(key)) for key in ("source_doctype", "source_name") if doc.get(key)))
        p("Incident and immediate response", "Heading2")
        field("What happened", doc.get("description"))
        field("Immediate response", doc.get("immediate_response"))
        field("Reportability assessment", doc.get("regulatory_review"))
        field("Assessment basis", doc.get("reportability_notes"))
        field("Regulator", doc.get("regulator"))
        field("Regulator reference", doc.get("regulator_reference"))
        p("Investigation team", "Heading2")
        field("Lead investigator", doc.get("lead_investigator"))
        field("Independent reviewer", doc.get("reviewer"))
        for row in doc.get("team") or []:
            field(text(row.get("team_role")), row.get("user"))
        p("Report guide", "Heading2")
        p("The workflow maps show the event sequence and recorded causal links. Complete narratives, evidence references, action outcomes and decisions follow the maps. The evidence appendix contains photographs, document pages and embedded original files. Draft hypotheses and unsupported findings remain identified as such.")
        return story

    p("Evidence register", "Heading2")
    for row in doc.get("evidence") or []:
        p(f"{row['entry_id']} - {row.get('title') or 'Evidence'}", "Heading3")
        for key, label in (("evidence_type", "Category"), ("observed_at", "Observed"), ("notes", "Observations"),
            ("file", "Attachment"), ("verification_status", "Verification status"), ("verification_notes", "Verification basis"),
            ("recorded_by", "Recorded by"), ("verified_by", "Verified by"), ("verified_on", "Verified on")):
            if row.get(key):
                field(label, row[key])
    p("Event timeline - full narratives", "Heading2")
    for row in ordered_timeline(doc.get("timeline")):
        p(f"{row['entry_id']} - {event_type(row, doc)}", "Heading3")
        field("Event time", row.get("event_datetime"))
        p(row.get("description"))
        field("Evidence", row.get("evidence_refs"))
        if row.get("previous_events"):
            field("Connected preceding events", row["previous_events"])
        if row.get("next_events"):
            field("Connected events", row["next_events"])
    if doc.get("method") != "ICAM":
        p("5 Whys - full narratives", "Heading2")
        for row in doc.get("five_whys") or []:
            p(f"{row['entry_id']} - {row.get('finding_status') or 'Hypothesis'}" + (" - Root cause" if checked(row.get("is_root_cause")) else ""), "Heading3")
            field("Preceding why / starting event", row.get("parent_id") or "Actual event")
            p(row.get("description"))
            field("Evidence", row.get("evidence_refs"))
            if checked(row.get("is_root_cause")):
                field("Stopping rationale", row.get("root_cause_reason"))
    if doc.get("method") != "5 Whys":
        p("ICAM - full narratives", "Heading2")
        for category in ICAM_CATEGORIES:
            p(category, "Heading3")
            for row in doc.get("icam_factors") or []:
                if row.get("category") != category:
                    continue
                field(row["entry_id"], row.get("finding_status"))
                if row.get("factor_type"):
                    field("Classification", row["factor_type"])
                p(row.get("description"))
                field("Evidence", row.get("evidence_refs"))
                field("Contributes to", row.get("contributes_to") or ("Actual event (defence)" if category == ICAM_CATEGORIES[0] else "No connection recorded"))
            reason = next((row.get("no_finding_reason") for row in doc.get("category_reviews") or [] if row.get("category") == category), "")
            if reason:
                field("Category review", reason)
    p("Findings and lessons", "Heading2")
    field("Findings", doc.get("findings_summary"))
    field("Lessons learned", doc.get("lessons_learned"))
    p("Corrective actions and effectiveness", "Heading2")
    for row in doc.get("actions") or []:
        p(f"{row['entry_id']} - {row.get('title') or 'Action'}", "Heading3")
        for key, label in (("action_status", "Status"), ("details", "Implementation details"), ("finding_refs", "Findings"),
            ("control_type", "Control"), ("priority", "Priority"), ("assigned_to_user", "Owner"), ("due_date", "Due"),
            ("verifier", "Independent verifier"), ("verification_due_date", "Verification due"), ("success_criteria", "Effectiveness criteria"),
            ("completion_notes", "Completion evidence"), ("completion_file", "Completion attachment"),
            ("completed_by", "Completed by"), ("completed_on", "Completed on"), ("verification_notes", "Effectiveness review"),
            ("verified_by", "Verified by"), ("verified_on", "Verified on"), ("cancellation_reason", "Cancellation reason")):
            if row.get(key):
                field(label, row[key])
    p("Review and close-out", "Heading2")
    for key, label in (("review_notes", "Review decision"), ("approved_by", "Approved by"), ("approved_on", "Approved on"),
        ("closure_summary", "Close-out summary"), ("closed_by", "Closed by"), ("closed_on", "Closed on")):
        field(label, doc.get(key))
    p("Workflow history", "Heading2")
    for row in doc.get("history") or []:
        p(f"{row.get('recorded_at')} | {row.get('actor')} | {row.get('event')}", "Heading3")
        p(row.get("notes"))
    return story


def _diagram_sheets(graph, mode):
    page_width, page_height = landscape(A4)
    sheets = []
    if mode == "whys":
        # Tile the same tree columns and depths as the editor, without shrinking
        # a large investigation to illegible text. Half columns centre forks.
        groups = {}
        for node in graph["nodes"]:
            groups.setdefault(int(node["column"] // 3), []).append(node)
        col_width = (page_width - 72) / 3.5
        w, h = col_width - 22, 128
        for group in sorted(groups):
            branch_nodes = groups[group]
            first = min(node["column"] for node in branch_nodes)
            last = max(node["column"] for node in branch_nodes)
            left = (page_width - ((last - first) * col_width + w)) / 2
            first_depth = min(node["depth"] for node in branch_nodes)
            for offset in range(first_depth, max(node["depth"] for node in branch_nodes) + 1, 3):
                nodes = [node for node in branch_nodes if offset <= node["depth"] < offset + 3]
                if nodes:
                    sheets.append({"nodes": nodes, "w": w, "h": h, "col_width": col_width,
                        "headers": [(36, "Causal branches run across; follow each why downward to its root cause.")],
                        "points": {node["id"]: (left + (node["column"] - first) * col_width,
                            page_height - 238 - (node["depth"] - offset) * 151) for node in nodes}})
        return sheets

    grouped = {index: [node for node in graph["nodes"] if node["lane"] == index] for index in range(len(graph["lanes"]))}
    # Fixed-size landscape sheets preserve readable text for deep/large graphs.
    # A link spanning sheets is printed with its destination's map number.
    columns = 5 if mode == "icam" else 4
    for start in range(0, len(graph["lanes"]), columns):
        lane_ids = list(range(start, min(start + columns, len(graph["lanes"]))))
        rows = max(1, max(len(grouped[lane]) for lane in lane_ids))
        for offset in range(0, rows, 3):
            nodes = [node for lane in lane_ids for node in grouped[lane][offset:offset + 3]]
            if not nodes:
                continue
            col_width = (page_width - 72) / len(lane_ids)
            points, headers = {}, []
            for index, lane in enumerate(lane_ids):
                x = 36 + index * col_width
                headers.append((x, graph["lanes"][lane]))
                for row_index, node in enumerate(grouped[lane][offset:offset + 3]):
                    points[node["id"]] = (x, page_height - 252 - row_index * 143)
            sheets.append({"nodes": nodes, "points": points, "headers": headers,
                "w": col_width - 22, "h": 128, "col_width": col_width})
    return sheets


def _diagram_pdf(doc, mode, styles):
    graph = diagram(doc, mode)
    sheets = _diagram_sheets(graph, mode)
    locations = {node["id"]: number for number, sheet in enumerate(sheets, 1) for node in sheet["nodes"]}
    output = BytesIO()
    c = canvas.Canvas(output, pagesize=landscape(A4))
    page_width, page_height = landscape(A4)
    palette = {"Event information": ("#eff6ff", "#3b82f6"), "Contributing factor": ("#fffbeb", "#ca8a04"),
        "Direct factor": ("#fff7ed", "#f97316"), "Actual event": ("#fff1f2", "#f43f5e"),
        "Post event": ("#ecfdf5", "#10b981"), "Root cause": ("#f5f3ff", "#8b5cf6")}
    title = {"timeline": "Event timeline", "whys": "5 Whys causal workflow", "icam": "ICAM causal workflow"}[mode]
    font = styles["BodyText"].fontName
    small = ParagraphStyle("MapNode", fontName=font, fontSize=8, leading=11, splitLongWords=True)

    def draw_text(value, x, y, width, size=8, limit=6):
        # Fit a concise map summary; the full, unabridged text is in the body.
        value = text(value)
        while True:
            p = _paragraph(value, ParagraphStyle("MapText", parent=small, fontSize=size, leading=size + 3))
            _, h = p.wrap(width, 1000)
            if h <= (size + 3) * limit or not value:
                break
            value = value[:-12].rstrip(" .") + "..." if len(value) > 16 else "..."
        p.drawOn(c, x, y - h)
        return h

    for number, sheet in enumerate(sheets, 1):
        c.setFillColor(colors.HexColor("#18354a"))
        c.setFont(font, 17)
        c.drawString(36, page_height - 36, f"{title} - map {number} / {len(sheets)}")
        draw_text(f"{doc.get('name')} | {doc.get('title')}", 36, page_height - 47, page_width - 72, 8, 1)
        draw_text("Map summaries; complete narratives follow. Dashed lines: " + ("time sequence." if mode == "timeline" else "unconfirmed findings. Arrows follow the recorded analysis."), 36, page_height - 63, page_width - 72, 8, 1)
        nodes, points = sheet["nodes"], sheet["points"]
        w, h, col_width = sheet["w"], sheet["h"], sheet["col_width"]
        for x, label in sheet["headers"]:
            draw_text(label, x, page_height - 86, page_width - 72 if mode == "whys" else w, 8, 3)
        # Connectors are behind the bubbles, just as in the interactive canvas.
        for edge_index, edge in enumerate(graph["edges"]):
            if edge["from"] not in points or edge["to"] not in points:
                continue
            ax, ay = points[edge["from"]]
            bx, by = points[edge["to"]]
            c.setStrokeColor(colors.HexColor("#64748b")); c.setLineWidth(1)
            c.setDash(4, 3) if edge["dashed"] else c.setDash()
            path = c.beginPath()
            if mode == "whys":
                ax += w / 2; bx += w / 2; by += h
                mid = (ay + by) / 2
                path.moveTo(ax, ay); path.curveTo(ax, mid, bx, mid, bx, by)
            else:
                skip_lane = abs(bx - ax) > col_width * 1.5
                track = min(ay, by) - 5 - (edge_index % 3) * 3
                ay += h / 2; by += h / 2
                if bx > ax:
                    ax += w
                elif bx < ax:
                    bx += w
                else:
                    ax += w; bx += w
                path.moveTo(ax, ay)
                mid = (ax + bx) / 2 if ax != bx else ax + 12
                if skip_lane:
                    direction = 1 if bx > ax else -1
                    exit_x, entry_x = ax + direction * 7, bx - direction * 7
                    path.lineTo(exit_x, ay); path.lineTo(exit_x, track)
                    path.lineTo(entry_x, track); path.lineTo(entry_x, by); path.lineTo(bx, by)
                else:
                    path.curveTo(mid, ay, mid, by, bx, by)
            c.drawPath(path)
            c.setDash()
            c.setFillColor(colors.HexColor("#64748b"))
            arrow = c.beginPath(); arrow.moveTo(bx, by)
            if mode == "whys":
                arrow.lineTo(bx - 3, by + 5); arrow.lineTo(bx + 3, by + 5)
            else:
                direction = 1 if bx >= ax else -1
                arrow.lineTo(bx - direction * 5, by + 3); arrow.lineTo(bx - direction * 5, by - 3)
            arrow.close()
            c.drawPath(arrow, fill=1, stroke=0)
        for node in nodes:
            x, y = points[node["id"]]
            fill, stroke = palette[node["kind"]]
            c.setFillColor(colors.HexColor(fill)); c.setStrokeColor(colors.HexColor(stroke)); c.setLineWidth(1.3)
            c.setDash(3, 2) if node["status"] == "Not supported" else c.setDash()
            c.roundRect(x, y, w, h, 12, fill=1, stroke=1); c.setDash()
            c.setFillColor(colors.HexColor("#18354a"))
            draw_text(node["title"], x + 9, y + h - 10, w - 18, 8, 2)
            draw_text(node["description"], x + 9, y + h - 36, w - 18, 8, 4)
            draw_text(f"{node['id']} | {node['status'] or node['time']}", x + 9, y + 37, w - 18, 6.5, 1)
            targets = [edge["to"] for edge in graph["edges"] if edge["from"] == node["id"] and (mode != "whys" or edge["to"] not in points)]
            sources = [edge["from"] for edge in graph["edges"] if mode == "whys" and edge["to"] == node["id"] and edge["from"] not in points]
            links = [label + ", ".join(f"{entry} (map {locations[entry]})" for entry in entries)
                for label, entries in (("From: ", sources), ("To: ", targets)) if entries]
            if links:
                draw_text("\n".join(links), x + 9, y + 25, w - 18, 6.5, 2)
        c.setFont(font, 7); c.setFillColor(colors.HexColor("#526478"))
        c.drawString(36, 20, "VERTO | CONFIDENTIAL | Cross-sheet connections are identified by reference and map number.")
        c.showPage()
    c.save()
    return output.getvalue()


def _attachment_pages(item, styles):
    content, filename = item["content"], item["file_name"]
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted and not reader.decrypt(""):
            return None, "Password-protected PDF. The original is embedded; a password is required to read it."
        if len(reader.pages) > MAX_PAGES:
            raise ReportLimitError("An evidence PDF exceeds the 1000-page report limit.")
        # Keep forms in separate namespaces when multiple evidence PDFs contain
        # fields with the same name. Originals, including signatures, stay intact.
        if reader.get_fields():
            reader.add_form_topname(item["appendix_id"])
        return reader, "All PDF pages follow. The unmodified original is also embedded."
    story = []
    if suffix in IMAGE_EXTENSIONS:
        with PILImage.open(BytesIO(content)) as source:
            if source.width * source.height > 30_000_000:
                return None, "Image exceeds the preview pixel limit. The original image is embedded."
            # GIFs use their representative first frame; multi-page TIFFs retain
            # every page in the printable appendix.
            frames = ImageSequence.Iterator(source) if suffix in {".tif", ".tiff"} else [source]
            for index, frame in enumerate(frames):
                if index >= MAX_PAGES:
                    raise ReportLimitError("An evidence image exceeds the 1000-page report limit.")
                picture = ImageOps.exif_transpose(frame).convert("RGB")
                buffer = BytesIO(); picture.save(buffer, format="PNG"); buffer.seek(0)
                image = Image(buffer)
                image._restrictSize(A4[0] - 84, A4[1] - 115)
                story.extend([_paragraph(f"{item['appendix_id']} | {filename}" + (f" | image {index + 1}" if suffix in {".tif", ".tiff"} else ""), styles["Heading3"]), image])
        return PdfReader(BytesIO(_render(story, styles, filename))), "Image preview follows; the original image is embedded."
    if suffix == ".docx":
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph as WordParagraph

        with ZipFile(BytesIO(content)) as archive:
            if sum(info.file_size for info in archive.infolist()) > 30 * 1024 * 1024:
                return None, "Document exceeds the preview limit. The complete original is embedded."
        source = Document(BytesIO(content))
        story.append(_paragraph("Word document text preview. Open the embedded original for the source layout, images and formatting.", styles["SmallNote"]))
        for element in source.element.body.iterchildren():
            if element.tag.endswith("}p"):
                story.append(_paragraph(WordParagraph(element, source).text, styles["BodyText"]))
            elif element.tag.endswith("}tbl"):
                table = Table(element, source)
                # Linear cell previews remain legible even for very wide source
                # tables, and can split over pages without losing cell contents.
                for index, row in enumerate(table.rows, 1):
                    story.append(_paragraph(f"Table row {index}", styles["Heading3"]))
                    for cell in row.cells:
                        story.append(_paragraph(cell.text, styles["BodyText"]))
        return PdfReader(BytesIO(_render(story, styles, filename))), "Word document text preview follows; the complete original is embedded."
    if suffix in {".txt", ".csv", ".log", ".md"}:
        if len(content) > 2 * 1024 * 1024:
            return None, "Text file exceeds the preview limit. The complete original is embedded."
        value = content.decode("utf-8-sig")
        story = [_paragraph(line, styles["BodyText"]) for line in value.splitlines()] or [_paragraph("Empty file", styles["BodyText"])]
        return PdfReader(BytesIO(_render(story, styles, filename))), "Text preview follows; the original file is embedded."
    return None, "Original file embedded in this PDF. Open its Attachments panel in a PDF reader to view this file type."


def build_report(doc, attachments=()):
    """Build from a saved dictionary; never trust browser-supplied report HTML."""
    if sum(len(item["content"]) for item in attachments) > MAX_BYTES:
        raise ReportLimitError("The evidence exceeds the 100 MB report limit.")
    styles = _styles()
    writer = PdfWriter()

    def append(source, title):
        reader = PdfReader(BytesIO(source)) if isinstance(source, bytes) else source
        if len(writer.pages) + len(reader.pages) > MAX_PAGES:
            raise ReportLimitError("The report exceeds 1000 pages.")
        writer.append(reader, outline_item=title, import_outline=False)

    append(_render(_details(doc, styles, overview=True), styles, doc.get("title") or "Investigation"), "Incident overview")
    append(_diagram_pdf(doc, "timeline", styles), "Event timeline")
    if doc.get("method") != "ICAM":
        append(_diagram_pdf(doc, "whys", styles), "5 Whys workflow")
    if doc.get("method") != "5 Whys":
        append(_diagram_pdf(doc, "icam", styles), "ICAM workflow")
    append(_render(_details(doc, styles), styles, "Investigation details"), "Evidence, analysis, actions and decisions")
    index = [_paragraph("Evidence appendix", styles["Heading1"]), _paragraph(
        "Photos and supported document previews follow in appendix order. Every original file is embedded in this PDF. Some browsers and mobile PDF viewers do not expose embedded files; use a PDF reader with an Attachments panel. Embedded originals retain their source content and any signatures; combined pages are report copies.", styles["BodyText"])]
    prepared = []
    for number, source in enumerate(attachments, 1):
        item = dict(source, appendix_id=f"APP-{number:03}")
        try:
            reader, note = _attachment_pages(item, styles)
        except ReportLimitError:
            raise
        except Exception:
            # Unpreviewable evidence stays present, with an explicit printed
            # explanation, instead of silently disappearing from the report.
            reader, note = None, "A printable preview could not be generated. The original file is embedded in this PDF."
        item.update(reader=reader, note=note)
        prepared.append(item)
        index.extend([_paragraph(f"{item['appendix_id']} - {item['file_name']}", styles["Heading3"]),
            _paragraph("References: " + (", ".join(item.get("references") or []) or "Additional investigation attachment"), styles["BodyText"]),
            _paragraph(note, styles["SmallNote"])])
    if not prepared:
        index.append(_paragraph("No file attachments were recorded for this investigation.", styles["BodyText"]))
    append(_render(index, styles, "Evidence appendix"), "Evidence appendix index")
    for item in prepared:
        title = f"{item['appendix_id']} - {item['file_name']}"
        cover = [_paragraph(title, styles["Heading1"]),
            _paragraph("References: " + (", ".join(item.get("references") or []) or "Additional investigation attachment"), styles["BodyText"]),
            _paragraph(item["note"], styles["BodyText"])]
        append(_render(cover, styles, title), title)
        if item["reader"] is not None:
            append(item["reader"], f"{item['appendix_id']} content")
        # Appendix prefixes keep attachments with duplicate filenames distinct.
        writer.add_attachment(f"{item['appendix_id']}-{Path(item['file_name']).name}", item["content"])
    for number, page in enumerate(writer.pages, 1):
        if page.rotation:
            page.transfer_rotation_to_content()
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        footer = BytesIO()
        c = canvas.Canvas(footer, pagesize=(width, height))
        c.setFont("Helvetica", 6)
        c.setFillColor(colors.HexColor("#526478"))
        c.drawRightString(width - 18, 9, f"Report page {number} / {len(writer.pages)}")
        c.save()
        page.merge_page(PdfReader(BytesIO(footer.getvalue())).pages[0])
    writer.add_metadata({"/Title": text(doc.get("title")), "/Author": "Verto Investigations", "/Subject": text(doc.get("name"))})
    output = BytesIO()
    writer.write(output)
    if output.tell() > MAX_BYTES:
        raise ReportLimitError("The complete PDF exceeds the 100 MB report limit.")
    return output.getvalue()
