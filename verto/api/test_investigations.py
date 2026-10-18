from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, now_datetime, today

from verto import access, default_apps
from verto.api import investigations as api


class IntegrationTestInvestigations(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        self.original_user = frappe.session.user
        frappe.set_user("Administrator")
        self.addCleanup(frappe.set_user, self.original_user)
        access.ensure_access_roles_and_profiles()
        self.lead = self._user(api.INVESTIGATOR)
        self.reviewer = self._user(api.MANAGER)
        self.outsider = self._user(api.INVESTIGATOR)
        self.observer = self._user(api.INVESTIGATOR)

    def _user(self, role):
        name = f"investigation-{frappe.generate_hash(length=10)}@example.test"
        frappe.get_doc({"doctype": "User", "email": name, "first_name": "Investigation Test", "enabled": 1,
            "send_welcome_email": 0, "user_type": "System User", "roles": [{"role": role}]}).insert(ignore_permissions=True)
        return name

    def _draft(self, complete=False):
        frappe.set_user(self.lead)
        data = {"title": "Synthetic alignment incident", "incident_datetime": str(now_datetime()), "method": "5 Whys",
            "lead_investigator": self.lead, "reviewer": self.reviewer,
            "team": [{"user": self.observer, "team_role": "Observer"}]}
        if complete:
            data.update({"description": "The coupling moved during alignment.", "immediate_response": "Stopped and isolated the equipment.",
                "due_date": add_days(today(), 7), "findings_summary": "The changed scope had no assigned reviewer.",
                "lessons_learned": "Define change review ownership.", "regulatory_review": "Not reportable",
                "reportability_notes": "Assessment recorded by the responsible manager.",
                "evidence": [{"entry_id": "E-000000000001", "title": "Change procedure", "notes": "The procedure has no review-owner field.",
                    "verification_status": "Verified", "verification_notes": "Compared current controlled procedure with the work pack."}],
                "five_whys": [{"entry_id": "W-000000000001", "description": "Change-review responsibility was not assigned.",
                    "finding_status": "Supported", "evidence_refs": "E-000000000001", "is_root_cause": 1,
                    "root_cause_reason": "Verified the omission in the controlled change process."}],
                "actions": [{"entry_id": "A-000000000001", "title": "Assign and trial a change-review owner", "assigned_to_user": self.lead,
                    "verifier": self.reviewer, "due_date": add_days(today(), 7), "verification_due_date": add_days(today(), 14),
                    "control_type": "Administrative", "success_criteria": "Sample three changed work packs and confirm review ownership.",
                    "finding_refs": "W-000000000001"}]})
        return api.save_investigation(data)

    def _approve(self):
        doc = self._draft(complete=True)
        doc = api.transition(doc["name"], "submit_review", doc["modified"])
        frappe.set_user(self.reviewer)
        return api.transition(doc["name"], "approve", doc["modified"], "Reviewed the evidence, causal analysis and action criteria.")

    def test_schema_and_launcher_are_installed(self):
        for doctype in (api.DOCTYPE, "EHS ICAM Factors", "Investigation Evidence", "Investigation Action"):
            self.assertTrue(frappe.db.exists("DocType", doctype))
        self.assertEqual(frappe.get_meta("EHS Incident").get_field("icam_factors").options, "EHS ICAM Factors")
        self.assertTrue(access.can_view_investigations_app())
        cards = default_apps.get_apps()
        self.assertEqual(len([card for card in cards if card.get("name") == default_apps.INVESTIGATIONS_APP]), 1)
        self.assertEqual(frappe.get_meta(api.DOCTYPE).track_changes, 1)

    def test_unassigned_investigator_cannot_list_or_fetch_another_investigation(self):
        doc = self._draft()
        frappe.set_user(self.outsider)
        self.assertNotIn(doc["name"], [row.name for row in api.list_investigations()["items"]])
        with self.assertRaises(frappe.PermissionError):
            api.get_investigation(doc["name"])
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            api.get_bootstrap()

    def test_observer_has_read_access_but_cannot_edit(self):
        doc = self._draft()
        frappe.set_user(self.observer)
        self.assertFalse(api.get_investigation(doc["name"])["capabilities"]["can_edit"])
        with self.assertRaises(frappe.PermissionError):
            api.save_investigation(dict(doc, title="Attempted change"), doc["modified"])

    def test_stale_saves_and_forged_workflow_flags_are_rejected(self):
        doc = self._draft()
        with self.assertRaises(frappe.TimestampMismatchError):
            api.save_investigation(dict(doc, title="Stale change"), "2000-01-01 00:00:00")
        stored = frappe.get_doc(api.DOCTYPE, doc["name"])
        stored.status = "Closed"
        stored.flags.verto_investigation_mutation = "workflow"
        with self.assertRaises(frappe.PermissionError):
            stored.save()
        self.assertEqual(frappe.db.get_value(api.DOCTYPE, doc["name"], "status"), "Draft")

    def test_review_requires_evidence_and_an_independent_manager(self):
        doc = self._draft()
        with self.assertRaises(frappe.ValidationError):
            api.transition(doc["name"], "submit_review", doc["modified"])
        doc = self._draft(complete=True)
        self.assertEqual(doc["readiness"], [])
        doc = api.transition(doc["name"], "submit_review", doc["modified"])
        with self.assertRaises(frappe.PermissionError):
            api.transition(doc["name"], "approve", doc["modified"], "Self approval")
        with self.assertRaises(frappe.ValidationError):
            api.save_investigation(dict(doc, findings_summary="Attempted edit under review"), doc["modified"])

    def test_completion_effectiveness_close_and_reopen_preserve_history(self):
        doc = self._approve()
        self.assertFalse(doc["actions"][0]["can_complete"])
        with self.assertRaises(frappe.ValidationError):
            api.transition(doc["name"], "close", doc["modified"], "Premature close")
        frappe.set_user(self.lead)
        doc = api.update_action(doc["name"], "A-000000000001", "complete", doc["modified"], "The controlled procedure was updated and trialled.")
        self.assertEqual(doc["actions"][0]["action_status"], "Completed")
        self.assertTrue(doc["closure_readiness"])
        with self.assertRaises(frappe.PermissionError):
            api.update_action(doc["name"], "A-000000000001", "verify", doc["modified"], "Attempted self verification")
        frappe.set_user(self.reviewer)
        doc = api.update_action(doc["name"], "A-000000000001", "verify", doc["modified"], "Sampled three changed work packs: all had the assigned review.")
        self.assertEqual(doc["closure_readiness"], [])
        self.assertEqual(doc["open_actions"], 0)
        doc = api.transition(doc["name"], "close", doc["modified"], "Actions implemented and independently verified effective.")
        self.assertEqual(doc["status"], "Closed")
        history = len(doc["history"])
        doc = api.transition(doc["name"], "reopen", doc["modified"], "New evidence requires an additional causal branch.")
        self.assertEqual(doc["status"], "Reopened")
        self.assertFalse(doc["approved_by"])
        self.assertEqual(len(doc["history"]), history + 1)
        self.assertEqual(doc["actions"][0]["action_status"], "Verified")

    def test_ineffective_action_returns_to_work_instead_of_closing(self):
        doc = self._approve()
        frappe.set_user(self.lead)
        doc = api.update_action(doc["name"], "A-000000000001", "complete", doc["modified"], "Procedure updated.")
        frappe.set_user(self.reviewer)
        doc = api.update_action(doc["name"], "A-000000000001", "ineffective", doc["modified"], "Two sampled work packs still lacked a review owner.")
        self.assertEqual(doc["actions"][0]["action_status"], "In Progress")
        self.assertFalse(doc["actions"][0]["verified_by"])
        self.assertTrue(doc["closure_readiness"])

    def test_deactivated_reviewer_does_not_trap_a_submitted_investigation(self):
        doc = self._draft(complete=True)
        doc = api.transition(doc["name"], "submit_review", doc["modified"])
        frappe.set_user("Administrator")
        frappe.db.set_value("User", self.reviewer, "enabled", 0)
        frappe.set_user(self.lead)
        doc = api.transition(doc["name"], "withdraw_review", doc["modified"], "Appoint a replacement reviewer after the personnel change.")
        self.assertEqual(doc["status"], "Analysis")
        self.assertEqual(doc["history"][-1]["event"], "Withdraw Review")

    def test_manager_can_reassign_verification_without_erasing_completed_work(self):
        doc = self._approve()
        frappe.set_user(self.lead)
        doc = api.update_action(doc["name"], "A-000000000001", "complete", doc["modified"], "Updated procedure and work packs.")
        frappe.set_user("Administrator")
        doc = api.transition(doc["name"], "reopen", doc["modified"], "Personnel change requires a replacement verifier.")
        doc["team"].append({"user": self.outsider, "team_role": "Investigator"})
        doc = api.save_investigation(doc, doc["modified"])
        doc = api.update_action(doc["name"], "A-000000000001", "reassign", doc["modified"], "Replacement verifier appointed.", verifier=self.outsider)
        self.assertEqual(doc["actions"][0]["verifier"], self.outsider)
        self.assertEqual(doc["actions"][0]["completed_by"], self.lead)
        self.assertEqual(doc["actions"][0]["action_status"], "Completed")
        self.assertIn("Replacement verifier", doc["history"][-1]["notes"])

    def test_changed_verified_evidence_is_withdrawn_until_reverified(self):
        doc = self._draft(complete=True)
        self.assertEqual(doc["evidence"][0]["verified_by"], self.lead)
        doc["evidence"][0]["notes"] = "A different revision of the procedure was supplied."
        doc = api.save_investigation(doc, doc["modified"])
        self.assertEqual(doc["evidence"][0]["verification_status"], "Unverified")
        self.assertFalse(doc["evidence"][0]["verified_by"])
        self.assertTrue(doc["readiness"])

    def test_private_attachments_cannot_be_published_detached_or_deleted(self):
        from frappe.utils.file_manager import save_file
        doc = self._draft()
        uploaded = save_file("investigation-evidence.txt", frappe.generate_hash(), api.DOCTYPE, doc["name"], is_private=1)
        uploaded.is_private = 0
        with self.assertRaises(frappe.ValidationError):
            uploaded.save()
        uploaded.reload()
        uploaded.attached_to_doctype = None
        uploaded.attached_to_name = None
        with self.assertRaises(frappe.ValidationError):
            uploaded.save()
        uploaded.reload()
        with patch.object(type(uploaded), "_delete_file_on_disk") as delete_bytes:
            with self.assertRaises(frappe.PermissionError):
                uploaded.run_method("on_trash")
            delete_bytes.assert_not_called()
        self.assertTrue(frappe.db.exists("File", uploaded.name))

    def test_source_details_require_existing_source_permissions(self):
        frappe.set_user("Administrator")
        source = frappe.get_doc({"doctype": "EHS Incident", "title": "Restricted incident", "incident_datetime": now_datetime(), "reported_datetime": now_datetime(), "description": "Restricted source details."}).insert()
        frappe.set_user(self.outsider)
        with self.assertRaises(frappe.PermissionError):
            api.get_source_details("EHS Incident", source.name)

