"""Exercise real PDF output, evidence bytes and diagram pagination without Frappe."""

from io import BytesIO
import unittest
from unittest.mock import patch

from docx import Document
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from verto.safety.investigation_report import ReportLimitError, build_report
from verto.safety.investigation_rules import ICAM_CATEGORIES, validate_structure
from verto.safety.investigation_workflow import diagram, event_time_key, event_type, ordered_timeline


def sample():
    return {
        "name": "INV-TEST", "title": "Coupling movement during alignment", "method": "5 Whys + ICAM", "status": "Analysis",
        "description": "The coupling moved while the crew aligned the drive.", "incident_datetime": "2026-11-04 10:00:00",
        "incident_time_precision": "Exact", "immediate_response": "Stopped work and isolated the drive.",
        "lead_investigator": "lead@example.test", "reviewer": "reviewer@example.test", "team": [],
        "timeline": [{"entry_id": "T-000000000001", "event_datetime": "2026-11-04 09:00:00", "description": "Alignment work began."},
            {"entry_id": "T-000000000002", "event_datetime": "2026-11-04 10:15:00", "description": "Area isolated."}],
        "evidence": [{"entry_id": "E-000000000001", "title": "Work pack", "notes": "Scope review omitted.", "verification_status": "Verified"}],
        "five_whys": [{"entry_id": "W-000000000001", "description": "No movement barrier was specified.", "finding_status": "Supported", "evidence_refs": "E-000000000001"},
            {"entry_id": "W-000000000002", "parent_id": "W-000000000001", "description": "Change review had no owner.", "finding_status": "Supported", "is_root_cause": 1,
                "root_cause_reason": "Procedure confirmed the ownership gap.", "evidence_refs": "E-000000000001"}],
        "icam_factors": [{"entry_id": "F-000000000001", "category": ICAM_CATEGORIES[0], "factor_type": "DF4 - Guards or Barriers", "description": "No movement barrier.", "finding_status": "Supported"},
            {"entry_id": "F-000000000002", "category": ICAM_CATEGORIES[3], "description": "Review ownership gap.", "finding_status": "Hypothesis", "contributes_to": "F-000000000001"}],
        "actions": [{"entry_id": "A-000000000001", "title": "Assign change-review ownership", "action_status": "Open", "details": "Trial the revised review procedure."}],
        "history": [{"actor": "lead@example.test", "event": "Analysis started", "recorded_at": "2026-11-04 11:00:00", "notes": "Preserve source evidence."}],
        "category_reviews": [], "findings_summary": "Missing review assignment.", "lessons_learned": "Confirm scope review ownership.",
    }


def source_pdf(value="ORIGINAL ATTACHED PDF"):
    output = BytesIO()
    c = Canvas(output)
    c.drawString(50, 700, value)
    c.showPage(); c.drawString(50, 700, "Second evidence page"); c.save()
    return output.getvalue()


class TestInvestigationReport(unittest.TestCase):
    def test_complete_report_preserves_narratives_and_analysis_links(self):
        data = sample()
        data["description"] = '<img src="https://invalid.test/tracker"> & literal narrative'
        reader = PdfReader(BytesIO(build_report(data)))
        value = "\n".join(page.extract_text() for page in reader.pages)
        for expected in (data["description"], "DF4 - Guards or Barriers", "W-000000000001", "Procedure confirmed", "Preserve source evidence", "No file attachments"):
            self.assertIn(expected, value)
        self.assertTrue(any(float(page.mediabox.width) > float(page.mediabox.height) for page in reader.pages))
        for index, page in enumerate(reader.pages, 1):
            self.assertIn(f"Report page {index} / {len(reader.pages)}", page.extract_text())

    def test_pdf_pages_images_docx_and_unknown_types_are_all_present(self):
        image = BytesIO(); Image.new("RGB", (400, 240), "orange").save(image, "PNG")
        document = Document(); document.add_paragraph("ORIGINAL WORD NARRATIVE"); document.add_table(rows=1, cols=1).cell(0, 0).text = "WORD TABLE CELL"
        word = BytesIO(); document.save(word)
        sources = [("evidence.pdf", source_pdf()), ("photo.png", image.getvalue()), ("notes.docx", word.getvalue()),
            ("sensor.bin", b"original sensor bytes"), ("notes.txt", b"All source text retained")]
        reader = PdfReader(BytesIO(build_report(sample(), [{"file_name": name, "content": content, "references": ["E-000000000001"]} for name, content in sources])))
        text = "\n".join(page.extract_text() for page in reader.pages)
        for expected in ("ORIGINAL ATTACHED PDF", "Second evidence page", "ORIGINAL WORD NARRATIVE", "WORD TABLE CELL", "All source text retained", "sensor.bin", "APP-005"):
            self.assertIn(expected, text)
        for index, (name, content) in enumerate(sources, 1):
            self.assertEqual(reader.attachments[f"APP-{index:03}-{name}"][0], content)
        self.assertTrue(any(list(page.images) for page in reader.pages))

    def test_unpreviewable_and_encrypted_files_retain_original_bytes(self):
        encrypted = BytesIO(); writer = PdfWriter(); writer.add_blank_page(width=200, height=200); writer.encrypt("secret"); writer.write(encrypted)
        sources = [{"file_name": "bad.pdf", "content": b"not a pdf"}, {"file_name": "locked.pdf", "content": encrypted.getvalue()}]
        reader = PdfReader(BytesIO(build_report(sample(), sources)))
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn("preview could not be generated", text)
        self.assertIn("Password-protected PDF", text)
        self.assertEqual(reader.attachments["APP-001-bad.pdf"][0], b"not a pdf")
        self.assertEqual(reader.attachments["APP-002-locked.pdf"][0], encrypted.getvalue())

    def test_duplicate_names_are_distinguished_and_files_follow_report_body(self):
        reader = PdfReader(BytesIO(build_report(sample(), [{"file_name": "notes.txt", "content": value} for value in (b"ONE", b"TWO")])))
        self.assertEqual(reader.attachments["APP-001-notes.txt"], [b"ONE"])
        self.assertEqual(reader.attachments["APP-002-notes.txt"], [b"TWO"])
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertLess(text.index("Workflow history"), text.index("Evidence appendix\n"))

    def test_deep_and_wide_diagrams_paginate_with_destination_references(self):
        data = sample()
        for index in range(3, 15):
            data["five_whys"].append({"entry_id": f"W-{index:012}", "parent_id": f"W-{index - 1:012}", "finding_status": "Supported", "description": "A long systemic finding. " * 40})
        for index in range(3, 10):
            data["icam_factors"].append({"entry_id": f"F-{index:012}", "category": ICAM_CATEGORIES[3], "description": "A separate influence.", "finding_status": "Hypothesis", "contributes_to": "F-000000000001"})
        reader = PdfReader(BytesIO(build_report(data)))
        value = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn("map 4 /", value)
        self.assertIn("(map 2)", value)
        self.assertIn("W-000000000014", value)
        self.assertIn("A long systemic finding. " * 2, value.replace("\n", " "))

    def test_limits_raise_instead_of_silently_omitting_evidence(self):
        with patch("verto.safety.investigation_report.MAX_BYTES", 3):
            with self.assertRaises(ReportLimitError):
                build_report(sample(), [{"file_name": "big.bin", "content": b"1234"}])


class TestInvestigationWorkflow(unittest.TestCase):
    def test_timeline_is_horizontal_and_chronological_independent_of_type_or_saved_coordinates(self):
        data = sample()
        data["timeline"] = [
            {"entry_id": "T-late", "event_type": "Direct factor", "event_datetime": "2026-11-04 11:00", "graph_x": 1, "graph_y": 500},
            {"entry_id": "T-equal-a", "event_datetime": "2026-11-04T09:00"},
            {"entry_id": "T-undated", "event_datetime": ""},
            {"entry_id": "T-first", "event_type": "Contributing factor", "event_datetime": "2026-11-03 14:00:00"},
            {"entry_id": "T-equal-b", "event_datetime": "2026-11-04 09:00:00.000000"},
        ]
        original = [row["entry_id"] for row in data["timeline"]]
        graph = diagram(data, "timeline")
        self.assertEqual([row["id"] for row in graph["nodes"]], ["T-first", "T-equal-a", "T-equal-b", "incident", "T-late", "T-undated"])
        self.assertEqual([row["lane"] for row in graph["nodes"]], list(range(6)))
        self.assertEqual(graph["lanes"][-1], "Time not set")
        self.assertEqual([row["entry_id"] for row in data["timeline"]], original)
        self.assertEqual(event_time_key("2026-11-04T09:30"), event_time_key("2026-11-04 09:30:00.000000"))
        self.assertEqual(event_time_key("2026-02-30 09:30"), "")
        data["timeline"][0]["event_datetime"] = "2026-11-03 08:00"
        self.assertEqual(ordered_timeline(data["timeline"])[0]["entry_id"], "T-late")

    def test_report_timeline_narratives_follow_the_same_date_order_as_the_diagram(self):
        data = sample()
        data["timeline"] = [
            {"entry_id": "T-late", "event_datetime": "2026-11-04 11:00", "description": "LAST TIMED NARRATIVE"},
            {"entry_id": "T-undated", "description": "UNDATED NARRATIVE"},
            {"entry_id": "T-first", "event_datetime": "2026-11-03 08:00", "description": "FIRST TIMED NARRATIVE"},
        ]
        reader = PdfReader(BytesIO(build_report(data)))
        body = "\n".join(page.extract_text() for page in reader.pages).split("Event timeline - full narratives", 1)[1].split("5 Whys - full narratives", 1)[0]
        self.assertLess(body.index("FIRST TIMED NARRATIVE"), body.index("LAST TIMED NARRATIVE"))
        self.assertLess(body.index("LAST TIMED NARRATIVE"), body.index("UNDATED NARRATIVE"))

    def test_legacy_timeline_uses_chronology_without_asserting_causality(self):
        graph = diagram(sample(), "timeline")
        self.assertEqual([(edge["from"], edge["to"]) for edge in graph["edges"]], [("T-000000000001", "incident"), ("incident", "T-000000000002")])
        self.assertTrue(all(edge["dashed"] for edge in graph["edges"]))
        data = sample(); data["incident_time_precision"] = "Date only"
        self.assertEqual(event_type(data["timeline"][1], data), "Event information")
        self.assertFalse(any("incident" in (edge["from"], edge["to"]) for edge in diagram(data, "timeline")["edges"]))

    def test_explicit_branch_replaces_inferred_edges_and_validates_references(self):
        data = sample(); data["timeline"][0]["next_events"] = "incident\nT-000000000002"
        self.assertEqual(len(diagram(data, "timeline")["edges"]), 2)
        self.assertTrue(all(not edge["dashed"] for edge in diagram(data, "timeline")["edges"]))
        self.assertEqual(validate_structure(data), [])
        data["timeline"][1]["next_events"] = data["timeline"][0]["entry_id"]
        self.assertIn("circular", " ".join(validate_structure(data)))
        data["timeline"][1]["next_events"] = "missing"
        self.assertIn("no longer exists", " ".join(validate_structure(data)))

    def test_coordinates_and_bubble_types_are_validated(self):
        data = sample()
        for value in (float("nan"), float("inf"), -1, 20001, "oops"):
            data["timeline"][0]["graph_x"] = value
            self.assertIn("coordinates", " ".join(validate_structure(data)))
        data["timeline"][0]["graph_x"] = 250
        self.assertEqual(validate_structure(data), [])
        data["timeline"][0]["event_type"] = "Unknown"
        self.assertIn("bubble type", " ".join(validate_structure(data)))

    def test_the_actual_event_can_connect_to_post_event_bubbles_without_cycles(self):
        data = sample()
        data["timeline"][0]["next_events"] = "incident"
        data["timeline"][1]["previous_events"] = "incident"
        graph = diagram(data, "timeline")
        self.assertEqual([(edge["from"], edge["to"]) for edge in graph["edges"]],
            [("T-000000000001", "incident"), ("incident", "T-000000000002")])
        self.assertEqual(validate_structure(data), [])
        data["timeline"][1]["next_events"] = "incident"
        self.assertIn("circular", " ".join(validate_structure(data)))


if __name__ == "__main__":
    unittest.main()
