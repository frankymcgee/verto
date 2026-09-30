from unittest import TestCase

from verto.api.mobile import jha_risk_signals as risk


class TestRiskSignals(TestCase):
    def test_hyphens_plurals_and_case_match_mechanisms(self):
        found = risk.signals("Hands at PINCH-POINTS and in the line-of-fire of a suspended load")
        self.assertIn("Pinch Points", found["mechanisms"])
        self.assertIn("Line of Fire", found["mechanisms"])
        self.assertIn("Entanglement and Crushing", found["critical_risks"])
        self.assertIn("Lifting Operations", found["critical_risks"])

    def test_model_semantic_labels_work_without_literal_keywords(self):
        found = risk.signals("Fit a pump flange while the other person aligns it", mechanisms=["Pinch Points"])
        self.assertEqual(found["mechanisms"], ["Pinch Points"])

    def test_matching_uses_word_boundaries(self):
        self.assertNotIn("Loss of Containment", risk.signals("A leaflet is attached")['mechanisms'])
        self.assertEqual(risk.signals("Review the toolbox meeting"), {"critical_risks": [], "mechanisms": []})

    def test_invalid_or_excessive_tags_are_rejected(self):
        for value in [["invented risk"], ["Pinch Points"] * 31]:
            with self.assertRaises(ValueError):
                risk.tags(value, risk.MECHANISMS)

    def test_imported_semicolon_labels_are_canonical_and_deduplicated(self):
        self.assertEqual(risk.tags("line-of-fire; Pinch Points; line of fire", risk.MECHANISMS), ["Line of Fire", "Pinch Points"])

    def test_mechanism_outranks_broad_category_and_context(self):
        query = risk.signals("Pinch point when fitting pump flange")
        exact = dict(critical_risks="", mechanisms="Pinch Points", search_text="pump flange")
        broad = dict(critical_risks="Entanglement and Crushing", mechanisms="", search_text="pump flange")
        self.assertGreater(risk.rank_incident(exact, query, ['pump', 'flange'])[0], risk.rank_incident(broad, query, ['pump', 'flange'])[0])

    def test_fingerprint_changes_for_activity_or_exposure_corrections_only(self):
        step = dict(activity="Fit flange")
        hazard = dict(hazard_or_energy_source="Pinch points", critical_risk_categories="", exposure_mechanisms="")
        original = risk.fingerprint(step, hazard)
        hazard['existing_controls'] = 'Use alignment tooling'
        self.assertEqual(original, risk.fingerprint(step, hazard))
        hazard['hazard_or_energy_source'] = 'Chemical splash'
        self.assertNotEqual(original, risk.fingerprint(step, hazard))
        self.assertNotEqual(original, risk.fingerprint(dict(activity='Remove pump'), dict(hazard_or_energy_source='Pinch points')))

    def test_rich_text_is_plain_data(self):
        self.assertEqual(risk.plain_text('<p>Investigation &amp; actions</p>'), 'Investigation & actions')
        self.assertNotIn('<', risk.normalise_text('<script>alert(1)</script> pinch points'))
