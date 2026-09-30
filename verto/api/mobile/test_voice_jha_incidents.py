import json
from datetime import datetime
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase

from verto.api.mobile import jha_risk_signals as risk
from verto.api.mobile import voice_jha_incidents as incidents
from verto.safety.doctype.jha_incident_learning.jha_incident_learning import JHAIncidentLearning


def incident(name="PINCH", **values):
    return dict(name=name, modified="2026-09-01", source_system="INX InControl", source_reference=name,
                incident_date="2020-01-01", title="Pump alignment", incident_summary="Finger caught between flanges",
                critical_risks="Entanglement and Crushing", mechanisms="Pinch Points", search_text="finger pinch points pump alignment", **values)


def jha():
    values = {"incident_references": []}
    doc = Mock(name="JHA document")
    doc.name = "JHA-TEST"
    doc.revision = 1
    doc.flags = frappe._dict()
    doc.work_steps = [frappe._dict(sequence=1, idx=1, activity="Fit pump flange")]
    doc.hazards_and_controls = [frappe._dict(name="hazard-1", source_hazard_identifier="H-1", work_step_sequence=1,
                                           hazard_or_energy_source="Pinch points", critical_risk_categories="", exposure_mechanisms="")]
    doc.get.side_effect = lambda key, default=None: values.get(key, default)
    doc.set.side_effect = lambda key, value: values.__setitem__(key, value)
    doc.append.side_effect = lambda key, value: values.setdefault(key, []).append(frappe._dict(value))
    return doc, values


class TestIncidentRetrieval(TestCase):
    def setUp(self):
        self.enterContext(patch.object(frappe.db, "exists", return_value=True))
        self.permission = self.enterContext(patch.object(frappe, "has_permission", return_value=True))
        self.get_list = self.enterContext(patch.object(frappe, "get_list", return_value=[]))
        self.get_all = self.enterContext(patch.object(frappe, "get_all", return_value=[]))

    def test_permission_filtered_lookup_and_parent_scoped_actions(self):
        self.get_list.return_value = [incident()]
        self.get_all.return_value = [dict(parent="PINCH", source_action_reference="ACT-1",
                                         action_description="Provide alignment tooling", action_status="Open", effectiveness_notes="")]
        result = incidents.find_incident_learning("Pump flange pinch point")
        self.assertEqual(result['status'], 'matches')
        self.assertEqual(result['incidents'][0]['actions'][0]['action_status'], 'Open')
        self.assertEqual(result['incidents'][0]['source_reference'], 'PINCH')
        for call in self.get_list.call_args_list:
            self.assertEqual(call.args, (incidents.INCIDENT_DOCTYPE,))
            self.assertEqual(call.kwargs['filters'], {'available_for_jha': 1})
            self.assertNotIn('ignore_permissions', call.kwargs)
        self.assertEqual(self.get_all.call_args.kwargs['filters'], {
            'parent': ['in', ['PINCH']], 'parenttype': incidents.INCIDENT_DOCTYPE, 'parentfield': 'actions'})

    def test_denied_incident_access_queries_nothing(self):
        self.permission.return_value = False
        self.assertEqual(incidents.find_incident_learning('Pinch point')['status'], 'unavailable')
        self.get_list.assert_not_called()
        self.get_all.assert_not_called()

    def test_missing_dataset_is_explicitly_unavailable(self):
        with patch.object(frappe.db, 'exists', return_value=False):
            self.assertEqual(incidents.find_incident_learning('Pinch point')['status'], 'unavailable')
        self.get_list.assert_not_called()

    def test_no_match_does_not_return_an_invented_incident(self):
        result = incidents.find_incident_learning('Pinch points')
        self.assertEqual((result['status'], result['incidents']), ('no_matches', []))

    def test_missing_investigation_actions_remain_unknown(self):
        self.get_list.return_value = [incident()]
        evidence = incidents.find_incident_learning('Pinch points')['incidents'][0]
        self.assertFalse(evidence['actions_available'])
        self.assertEqual(evidence['actions'], [])
        self.assertEqual(evidence['investigation_findings'], '')

    def test_context_fallback_requires_two_matching_words(self):
        row = incident()
        row.update(critical_risks='', mechanisms='', search_text='pump alignment')
        self.get_list.return_value = [row]
        self.assertEqual(incidents.find_incident_learning('pump replacement')['status'], 'no_matches')
        self.assertEqual(incidents.find_incident_learning('pump alignment')['status'], 'matches')

    def test_exact_mechanism_beats_a_newer_broad_risk_and_limits_are_reported(self):
        rows = [incident(str(i)) for i in range(101)]
        rows[0].update(name='EXACT-OLDER', incident_date='2000-01-01', critical_risks='', mechanisms='Pinch Points')
        for row in rows[1:]:
            row.update(incident_date='2026-01-01', mechanisms='')
        self.get_list.return_value = rows
        result = incidents.find_incident_learning('Pinch point')
        self.assertTrue(result['search_limited'])
        self.assertEqual(len(result['incidents']), 3)
        self.assertEqual(result['incidents'][0]['name'], 'EXACT-OLDER')

    def test_reference_serialization_refilters_permissions_and_marks_source_changes(self):
        doc, _ = jha()
        self.get_list.return_value = [incident()]
        incidents.hazard_incident_learning(doc, doc.hazards_and_controls[0])
        self.get_list.return_value = [dict(incident(), modified='2026-09-30')]
        result = incidents.serialize_incident_learning(doc)
        self.assertTrue(result[0]['incidents'][0]['source_changed'])
        self.get_list.return_value = []
        result = incidents.serialize_incident_learning(doc)
        self.assertEqual((result[0]['status'], result[0]['incidents']), ('unavailable', []))

    def test_hazard_and_revision_changes_exclude_old_references(self):
        doc, _ = jha()
        incidents.hazard_incident_learning(doc, doc.hazards_and_controls[0])
        doc.hazards_and_controls[0].hazard_or_energy_source = 'Chemical splash'
        self.assertEqual(incidents.serialize_incident_learning(doc), [])
        doc.hazards_and_controls[0].hazard_or_energy_source = 'Pinch points'
        doc.revision = 2
        self.assertEqual(incidents.serialize_incident_learning(doc), [])

    def test_repeated_search_replaces_only_the_same_hazard_and_preserves_no_match(self):
        doc, values = jha()
        for _ in range(2):
            incidents.hazard_incident_learning(doc, doc.hazards_and_controls[0])
        self.assertEqual(len(values['incident_references']), 1)
        self.assertEqual(values['incident_references'][0].search_status, 'no_matches')
        self.assertEqual(json.loads(values['incident_references'][0].incident_matches), [])

    def test_lookup_failure_does_not_discard_the_confirmed_hazard(self):
        doc, values = jha()
        with patch.object(incidents, 'find_incident_learning', side_effect=RuntimeError('database unavailable')), patch.object(frappe, 'log_error'), patch.object(frappe, 'get_traceback', return_value='trace'):
            result = incidents.hazard_incident_learning(doc, doc.hazards_and_controls[0])
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(values['incident_references'][0].search_status, 'unavailable')
        doc.save.assert_not_called()

    def test_bad_semantic_labels_are_rejected_before_querying_records(self):
        with self.assertRaises(frappe.ValidationError):
            incidents.find_incident_learning('flange alignment', mechanisms=['Unknown'])
        self.get_list.assert_not_called()

    def test_read_tool_cannot_skip_steps_or_modify_draft(self):
        from verto.api.mobile import voice_jha_tools, voice_jha_progress
        doc, _ = jha()
        doc.jha_status = 'Draft'
        with patch.object(voice_jha_tools, '_require_login'), patch.object(voice_jha_tools, '_get_jha', return_value=doc), patch.object(voice_jha_progress, 'calculate_facilitation_progress', return_value={'current_step_sequence': 1}):
            with self.assertRaises(frappe.ValidationError):
                incidents.execute_incident_tool('JHA-TEST', {'work_step_sequence': 2, 'discussion_context': 'Pinch point'})
            result = incidents.execute_incident_tool('JHA-TEST', {'work_step_sequence': 1, 'discussion_context': 'Pinch point'})
        self.assertTrue(result['ok'])
        doc.save.assert_not_called()
        doc.set.assert_not_called()

    def test_audit_retains_references_and_replays_only_current_accessible_evidence(self):
        from verto.api.mobile import voice_jha_tools
        doc, values = jha()
        doc.meta.has_field.return_value = True
        self.get_list.return_value = [incident()]
        learning = incidents.hazard_incident_learning(doc, doc.hazards_and_controls[0])
        voice_jha_tools._append_audit(doc, 'CALL-1', 'record_hazard_and_control', {}, {'incident_learning': learning})
        values['voice_tool_audit_log'] = doc.voice_tool_audit_log
        saved = json.loads(doc.voice_tool_audit_log)[0]['result']['incident_learning']['incidents'][0]
        self.assertEqual(saved['name'], 'PINCH')
        self.assertNotIn('incident_summary', saved)
        replay = voice_jha_tools._find_audit_result(doc, 'CALL-1')
        self.assertEqual(replay['incident_learning']['incidents'][0]['source_reference'], 'PINCH')
        self.get_list.return_value = []
        replay = voice_jha_tools._find_audit_result(doc, 'CALL-1')
        self.assertEqual(replay['incident_learning']['incidents'], [])

    def test_hazard_write_looks_up_evidence_without_promoting_controls_or_risk_flags(self):
        from verto.api.mobile import voice_jha_tools
        doc, values = jha()
        row = doc.hazards_and_controls[0]
        row.set = lambda key, value: row.__setitem__(key, value)
        row.critical_risk = 0
        row.additional_controls = ''
        self.get_list.return_value = [dict(incident(), recommended_controls='Use alignment tooling')]
        result = voice_jha_tools._record_hazard_and_control(doc, {
            'hazard_identifier': 'H-1', 'work_step_identifier': 'step-1', 'work_step_sequence': 1,
            'existing_controls': 'Crew keeps hands clear',
        })
        self.assertEqual(result['incident_learning']['status'], 'matches')
        self.assertEqual(row.additional_controls, '')
        self.assertEqual(row.critical_risk, 0)
        self.assertEqual(len(values['incident_references']), 1)

    def test_clients_cannot_forge_incident_references(self):
        from verto.safety.doctype.digital_job_hazard_analysis.digital_job_hazard_analysis import DigitalJobHazardAnalysis
        doc, values = jha()
        doc.is_new.return_value = True
        values['incident_references'] = [frappe._dict(hazard_identifier='fake')]
        with self.assertRaises(frappe.PermissionError):
            DigitalJobHazardAnalysis._validate_incident_references(doc)
        doc.flags.allow_jha_incident_mutation = True
        DigitalJobHazardAnalysis._validate_incident_references(doc)

    def test_unchanged_reference_survives_json_datetime_round_trip(self):
        from verto.safety.doctype.digital_job_hazard_analysis.digital_job_hazard_analysis import DigitalJobHazardAnalysis
        doc, values = jha()
        doc.is_new.return_value = False
        previous = frappe._dict(hazard_identifier='H-1', searched_at=datetime(2026, 9, 30, 8), work_step_sequence=1)
        doc.get_doc_before_save.return_value = frappe._dict(incident_references=[previous])
        values['incident_references'] = [frappe._dict(previous, searched_at='2026-09-30 08:00:00', work_step_sequence='1')]
        DigitalJobHazardAnalysis._validate_incident_references(doc)

    def test_incomplete_source_excerpts_are_identified(self):
        self.get_list.return_value = [dict(incident(), investigation_findings='a' * 4100)]
        evidence = incidents.find_incident_learning('Pinch point')['incidents'][0]
        self.assertTrue(evidence['evidence_excerpt'])
        self.assertEqual(len(evidence['investigation_findings']), 4000)


class TestIncidentImport(TestCase):
    def document(self, **values):
        doc = Mock()
        for key, value in dict(source_system=' INX InControl ', source_reference=' TEST-101 ', title='Flange alignment',
                               incident_summary='Finger crushed between pump flanges', critical_risks='', mechanisms='',
                               recommended_controls='Inspect lifting gear', **values).items():
            setattr(doc, key, value)
        doc.get_doc_before_save.return_value = None
        doc._source_key.side_effect = lambda: JHAIncidentLearning._source_key(doc)
        return doc

    def test_source_identity_is_stable_and_cannot_be_changed(self):
        doc = self.document()
        JHAIncidentLearning.autoname(doc)
        key = doc.name
        JHAIncidentLearning.validate(doc)
        self.assertEqual(key, doc.source_key)
        doc.source_reference = 'DIFFERENT'
        doc.get_doc_before_save.return_value = SimpleNamespace(source_key=key)
        with self.assertRaises(frappe.ValidationError):
            JHAIncidentLearning.validate(doc)

    def test_import_indexes_event_exposures_without_indexing_proposed_controls(self):
        doc = self.document()
        JHAIncidentLearning.validate(doc)
        self.assertIn('Caught Between', doc.indexed_mechanisms)
        self.assertIn('Entanglement and Crushing', doc.indexed_critical_risks)
        self.assertNotIn('Lifting Operations', doc.indexed_critical_risks)
        self.assertNotIn('lifting gear', doc.search_text)

    def test_corrected_incident_text_removes_stale_inferred_exposures(self):
        doc = self.document()
        JHAIncidentLearning.validate(doc)
        self.assertIn('Pinch Points', doc.indexed_mechanisms)
        doc.incident_summary = 'Oil spill from a leaking fitting'
        JHAIncidentLearning.validate(doc)
        self.assertNotIn('Pinch Points', doc.indexed_mechanisms)
        self.assertIn('Loss of Containment', doc.indexed_mechanisms)


class TestIncidentPermissions(TestCase):
    def test_only_enabled_lessons_are_readable_by_crews(self):
        with patch.object(frappe, 'get_roles', return_value=['All']):
            self.assertTrue(incidents.incident_has_permission(frappe._dict(available_for_jha=1), user='crew@example.test'))
            self.assertFalse(incidents.incident_has_permission(frappe._dict(available_for_jha=0), user='crew@example.test'))
            self.assertFalse(incidents.incident_has_permission(frappe._dict(available_for_jha=1), user='crew@example.test', ptype='write'))
            self.assertFalse(incidents.incident_has_permission(None, user='Guest'))
            self.assertIn('available_for_jha = 1', incidents.incident_query_conditions('crew@example.test'))

    def test_managers_can_maintain_disabled_lessons(self):
        self.assertTrue(incidents.incident_has_permission(frappe._dict(available_for_jha=0), user='Administrator', ptype='write'))
        self.assertEqual(incidents.incident_query_conditions('Administrator'), '')


class IntegrationTestIncidentLearning(IntegrationTestCase):
    def test_import_child_actions_retrieval_and_disabling_on_a_real_site(self):
        reference = f"TEST-JHA-{frappe.generate_hash(length=10)}"
        doc = frappe.get_doc({
            'doctype': incidents.INCIDENT_DOCTYPE, 'source_system': 'INX InControl',
            'source_reference': reference, 'title': 'Test flange alignment', 'incident_date': '2020-01-01',
            'incident_summary': 'Finger crushed between pump flanges at a pinch point.',
            'available_for_jha': 1,
            'actions': [{'action_description': 'Test alignment tooling', 'action_status': 'Open'}],
        }).insert(ignore_permissions=True)
        result = incidents.find_incident_learning('Pinch point at pump flanges')
        evidence = next(row for row in result['incidents'] if row['source_reference'] == reference)
        self.assertEqual(evidence['actions'][0]['action_status'], 'Open')
        self.assertIn('Pinch Points', evidence['mechanisms'])
        self.assertEqual(doc.name, doc.source_key)
        duplicate = frappe.get_doc({
            'doctype': incidents.INCIDENT_DOCTYPE, 'source_system': 'INX InControl',
            'source_reference': reference, 'title': 'Duplicate source', 'incident_summary': 'Same incident',
        })
        with self.assertRaises(frappe.DuplicateEntryError):
            duplicate.insert(ignore_permissions=True)
        doc.available_for_jha = 0
        doc.save(ignore_permissions=True)
        result = incidents.find_incident_learning('Pinch point at pump flanges')
        self.assertNotIn(reference, [row['source_reference'] for row in result['incidents']])
