import copy
import unittest

from verto.safety.investigation_rules import ICAM_CATEGORIES, closure_readiness, review_readiness, validate_structure
from verto.safety.icam import ICAM_FACTOR_CATEGORIES, ICAM_FACTOR_GROUPS


def ready_investigation():
    return {
        "method": "5 Whys", "description": "The coupling moved during alignment.", "immediate_response": "Stopped the work and isolated the equipment.",
        "lead_investigator": "lead@example.test", "reviewer": "reviewer@example.test", "due_date": "2026-11-01",
        "findings_summary": "The changed scope was not reviewed.", "lessons_learned": "Revalidate scope before work starts.",
        "regulatory_review": "Not reportable", "reportability_notes": "Recorded assessment by the responsible manager.",
        "evidence": [{"entry_id": "E-000000000001", "title": "Work pack", "verification_status": "Verified"}],
        "five_whys": [{"entry_id": "W-000000000001", "description": "The change process had no assigned owner.", "finding_status": "Supported", "evidence_refs": "E-000000000001", "is_root_cause": 1, "root_cause_reason": "Confirmed the missing assignment in the change procedure."}],
        "icam_factors": [], "timeline": [], "category_reviews": [],
        "actions": [{"entry_id": "A-000000000001", "title": "Assign a change-review owner", "action_status": "Open", "finding_refs": "W-000000000001", "assigned_to_user": "lead@example.test", "verifier": "reviewer@example.test", "due_date": "2026-11-03", "verification_due_date": "2026-11-10", "control_type": "Administrative", "success_criteria": "Sample three changes and confirm assigned review."}],
    }


class TestInvestigationRules(unittest.TestCase):
    def setUp(self):
        self.data = ready_investigation()

    def test_evidence_backed_branch_can_finish_before_five_questions(self):
        self.assertEqual(review_readiness(self.data), [])

    def test_five_is_not_a_hard_depth_limit(self):
        for number in range(2, 8):
            previous = self.data["five_whys"][-1]
            previous["is_root_cause"] = 0
            row = dict(previous, entry_id=f"W-{number:012}", parent_id=previous["entry_id"], is_root_cause=1)
            self.data["five_whys"].append(row)
        self.data["actions"][0]["finding_refs"] = self.data["five_whys"][-1]["entry_id"]
        self.assertEqual(review_readiness(self.data), [])

    def test_every_supported_leaf_needs_a_stopping_rationale(self):
        self.data["five_whys"].append(dict(self.data["five_whys"][0], entry_id="W-000000000002", is_root_cause=0))
        self.assertTrue(any("continue this supported branch" in error for error in review_readiness(self.data)))

    def test_hypotheses_and_disputed_evidence_cannot_support_review(self):
        self.data["evidence"][0]["verification_status"] = "Disputed"
        self.assertTrue(any("verified evidence" in error for error in review_readiness(self.data)))
        self.data["five_whys"][0]["finding_status"] = "Hypothesis"
        self.assertTrue(any("resolve the hypothesis" in error for error in review_readiness(self.data)))

    def test_why_cycles_and_orphans_are_rejected(self):
        self.data["five_whys"][0]["parent_id"] = "W-000000000001"
        self.assertTrue(any("circular" in error for error in validate_structure(self.data)))
        self.data["five_whys"][0]["parent_id"] = "W-000000000099"
        self.assertTrue(any("no longer exists" in error for error in validate_structure(self.data)))

    def test_missing_evidence_and_duplicate_references_are_rejected(self):
        self.data["evidence"] = []
        self.assertTrue(any("select evidence" in error for error in validate_structure(self.data)))
        self.data = ready_investigation()
        self.data["evidence"].append(copy.deepcopy(self.data["evidence"][0]))
        self.assertTrue(any("Duplicate reference" in error for error in validate_structure(self.data)))

    def test_oversized_graph_stops_before_traversal(self):
        self.data["five_whys"] *= 201
        self.assertTrue(any("200 entries" in error for error in validate_structure(self.data)))

    def test_all_root_causes_need_actions(self):
        self.data["actions"] = []
        self.assertTrue(any("link at least one corrective action" in error for error in review_readiness(self.data)))

    def test_owners_due_dates_control_type_and_independent_verifier_are_required(self):
        action = self.data["actions"][0]
        action["verifier"] = action["assigned_to_user"]
        action["due_date"] = ""
        self.assertTrue(any("independent action verifier" in error for error in review_readiness(self.data)))
        self.assertTrue(any("set due date" in error for error in review_readiness(self.data)))

    def test_icam_can_record_no_finding_in_a_category_without_inventing_a_cause(self):
        self.data["method"] = "ICAM"
        self.data["icam_factors"] = [{"entry_id": "F-000000000001", "category": ICAM_CATEGORIES[0], "description": "The changed alignment task had no specified barrier.", "finding_status": "Supported", "evidence_refs": "E-000000000001"}]
        self.data["category_reviews"] = [{"category": category, "no_finding_reason": "The available verified evidence did not identify a contributing factor."} for category in ICAM_CATEGORIES[1:]]
        self.data["actions"][0]["finding_refs"] = "F-000000000001"
        self.assertEqual(review_readiness(self.data), [])
        self.data["category_reviews"].pop()
        self.assertTrue(any("Organisational Factors" in error for error in review_readiness(self.data)))

    def test_icam_links_must_not_cycle_or_point_to_unsupported_factors(self):
        self.data["method"] = "ICAM"
        self.data["icam_factors"] = [{"entry_id": "F-000000000001", "category": ICAM_CATEGORIES[0], "description": "A defence failed", "finding_status": "Supported", "evidence_refs": "E-000000000001", "contributes_to": "F-000000000002"}, {"entry_id": "F-000000000002", "category": ICAM_CATEGORIES[3], "description": "Unconfirmed system issue", "finding_status": "Hypothesis", "contributes_to": "F-000000000001"}]
        self.assertTrue(any("circular" in error for error in validate_structure(self.data)))
        self.assertTrue(any("supported factors" in error for error in review_readiness(self.data)))

    def test_icam_catalogue_has_all_supplied_codes_in_order(self):
        codes = [[option.split(" - ")[0] for option in group["options"]] for group in ICAM_FACTOR_GROUPS]
        self.assertEqual(codes, [
            [f"DF{number}" for number in range(1, 17)],
            [f"IT{number}" for number in range(1, 15)],
            [f"TE{number}" for number in range(1, 27)],
            [f"HF{number}" for number in range(1, 27)],
            ["CM", "CO", "DE", "HW", "IG", "MC", "MM", "MS", "OC", "OL", "OR", "PR", "RM", "RI", "TR", "VM"],
        ])
        self.assertEqual(len(ICAM_FACTOR_CATEGORIES), 98)
        self.assertIn("HF13 - Secondary level", ICAM_FACTOR_CATEGORIES)
        self.assertIn("TE25 - Training", ICAM_FACTOR_CATEGORIES)
        self.assertIn("TE26 - Purchasing", ICAM_FACTOR_CATEGORIES)

    def test_every_icam_classification_is_accepted_only_in_its_category(self):
        for option, category in ICAM_FACTOR_CATEGORIES.items():
            for candidate in ICAM_CATEGORIES:
                with self.subTest(option=option, category=candidate):
                    self.data["icam_factors"] = [{"entry_id": "F-000000000001", "category": candidate,
                        "factor_type": option, "finding_status": "Hypothesis"}]
                    errors = validate_structure(self.data)
                    self.assertEqual(bool(errors), candidate != category)

    def test_unknown_icam_classifications_and_placeholder_are_rejected(self):
        for option in ("DF99 - Invented factor", "Select factor from list"):
            self.data["icam_factors"] = [{"entry_id": "F-000000000001", "category": ICAM_CATEGORIES[0],
                "factor_type": option, "finding_status": "Hypothesis"}]
            self.assertTrue(any("category's list" in error for error in validate_structure(self.data)))

    def test_completed_actions_do_not_count_as_effectiveness_verified(self):
        self.data["approved_by"] = "reviewer@example.test"
        self.data["actions"][0]["action_status"] = "Completed"
        self.assertTrue(closure_readiness(self.data))
        self.data["actions"][0]["action_status"] = "Verified"
        self.assertEqual(closure_readiness(self.data), [])

    def test_cancellations_require_a_recorded_reason_and_pending_reportability_blocks_closure(self):
        self.data["approved_by"] = "reviewer@example.test"
        self.data["actions"][0]["action_status"] = "Cancelled"
        self.assertTrue(any("cancellation" in error for error in closure_readiness(self.data)))
        self.data["actions"][0]["cancellation_reason"] = "Replaced by the verified engineering change."
        self.assertEqual(closure_readiness(self.data), [])
        self.data["regulatory_review"] = "Review required"
        self.assertTrue(any("reportability" in error for error in closure_readiness(self.data)))


if __name__ == "__main__":
    unittest.main()
