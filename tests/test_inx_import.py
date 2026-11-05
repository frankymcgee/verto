import unittest
from datetime import datetime

from verto.safety.inx_import import parse_rows, parse_workbook, source_key


HEADERS = [
    'Reference', 'Event Date', 'Reported By Name', 'Event Type', 'Event Sub Type',
    'RE Workgroup Name', 'Location', 'Country', 'Immediate Action Taken', 'Status',
    'Short Observation', 'Detailed Observation', 'Originator', 'Responsible Manager(s)',
    'Moderator Comment', 'Review Date', 'Reviewed Date', 'Review Summary',
    'Closed Out Date', 'Closed Out By', 'Reported By Lookup Name', 'Workgroup',
]


def event(**overrides):
    values = {
        'Reference': 'TEST-101', 'Event Date': datetime(2025, 1, 6, 3, 30),
        'Reported By Name': 'Synthetic reporter', 'Event Type': 'Injury', 'Event Sub Type': 'Work Related',
        'Location': 'Workshop', 'Country': 'Australia', 'Immediate Action Taken': 'Stopped the task',
        'Status': 'Closed', 'Short Observation': 'Hand caught between flanges',
        'Detailed Observation': 'Hand was in the pinch point while aligning the flange.',
        'Originator': 'Synthetic originator', 'Responsible Manager(s)': 'Synthetic manager',
        'Closed Out Date': datetime(2025, 1, 7, 10, 5, 7, 123000),
        'Closed Out By': 'Synthetic closer', 'Reported By Lookup Name': 'Synthetic lookup', 'Workgroup': 'Maintenance',
    }
    values.update(overrides)
    return [values.get(column) for column in HEADERS]


class TestINXExportParser(unittest.TestCase):
    def test_actual_report_layout_keeps_response_and_closure_without_inventing_actions(self):
        parsed = parse_rows([HEADERS, event()])
        row = parsed['records'][0]
        self.assertEqual(row['immediate_actions'], 'Stopped the task')
        self.assertEqual(row['event_status'], 'Closed')
        self.assertEqual(row['closed_out_datetime'], '2025-01-07 10:05:07.123000')
        self.assertEqual(row['review_summary'], '')
        self.assertEqual(parsed['missing_review_summaries'], 1)
        self.assertNotIn('investigation_actions', row)
        self.assertNotIn('recommended_controls', row)
        self.assertNotIn('Synthetic reporter', str(row))
        self.assertEqual(set(parsed['ignored_columns']), {
            'Reported By Name', 'Originator', 'Responsible Manager(s)', 'Closed Out By', 'Reported By Lookup Name',
        })

    def test_long_short_observations_are_preserved_without_a_data_field_truncation(self):
        title = 'Synthetic long observation ' * 10
        row = parse_rows([HEADERS, event(**{'Short Observation': title})])['records'][0]
        self.assertEqual(row['short_observation'], title.strip())

    def test_columns_can_be_reordered_and_unknown_columns_do_not_become_evidence(self):
        parsed = parse_rows([list(reversed(HEADERS)) + ['Extra'], list(reversed(event())) + ['Unmapped narrative']])
        self.assertEqual(parsed['records'][0]['source_reference'], 'TEST-101')
        self.assertNotIn('Unmapped narrative', str(parsed['records']))
        self.assertIn('Extra', parsed['ignored_columns'])

    def test_blank_optional_columns_and_rows_are_supported(self):
        required = ['Reference', 'Event Date', 'Short Observation', 'Detailed Observation', 'Immediate Action Taken']
        parsed = parse_rows([required, ['TEST-101', '06/01/2025', '', 'Pinch point', 'Stopped work'], [None] * 5])
        self.assertEqual(len(parsed['records']), 1)
        self.assertIsNone(parsed['records'][0]['reviewed_date'])
        self.assertEqual(parsed['records'][0]['event_datetime'], '2025-01-06 00:00:00')

    def test_missing_or_duplicate_headings_fail_before_mapping(self):
        for header in (HEADERS[1:], HEADERS + ['Reference']):
            with self.subTest(header=header):
                with self.assertRaises(ValueError):
                    parse_rows([header, event()])

    def test_duplicate_incidents_use_the_same_case_insensitive_trimmed_identity(self):
        with self.assertRaisesRegex(ValueError, 'duplicate incident reference'):
            parse_rows([HEADERS, event(), event(Reference=' test-101 ')])
        self.assertEqual(source_key(' INX InControl ', ' TEST-101 '), source_key('inx incontrol', 'test-101'))

    def test_invalid_reference_and_date_are_not_silently_skipped(self):
        for overrides in ({'Reference': None}, {'Event Date': None}, {'Event Date': 'not a date'}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    parse_rows([HEADERS, event(**overrides)])

    def test_personnel_changes_do_not_invalidate_a_reviewed_lesson_but_response_changes_do(self):
        original = parse_rows([HEADERS, event()])['records'][0]['source_fingerprint']
        person_changed = parse_rows([HEADERS, event(**{'Reported By Name': 'Another synthetic reporter'})])['records'][0]['source_fingerprint']
        response_changed = parse_rows([HEADERS, event(**{'Immediate Action Taken': 'Isolated the equipment'})])['records'][0]['source_fingerprint']
        self.assertEqual(original, person_changed)
        self.assertNotEqual(original, response_changed)

    def test_empty_and_unreadable_exports_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, 'no events'):
            parse_rows([HEADERS])
        with self.assertRaisesRegex(ValueError, 'readable INX XLSX'):
            parse_workbook(b'not an xlsx')


if __name__ == '__main__':
    unittest.main()
