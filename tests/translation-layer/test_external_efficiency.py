#!/usr/bin/env python3
"""M3 actual external-data arithmetic, provenance, uncertainty and failure tests."""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from compare_efficiency import external_pair_audit
spec = importlib.util.spec_from_file_location('external', ROOT/'scripts/external_efficiency.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def fixture():
    data = {'schema_version': 12, 'metadata': {'session_id': 'test', 'build_sha': 'abc-dirty',
            'device_identifier': 'iPad16,5', 'launch_configuration': {'requested_fps': 60}},
            'duration_seconds': 10, 'exclusions': []}
    manifest = m.template(data)
    manifest.update(clock_offset_seconds=0, clock_uncertainty_seconds=0,
                    clock_alignment_method='Synthetic shared clock, not a device measurement', max_gap_seconds=5)
    manifest['conditions'] = {k: 'synthetic unchanged' for k in manifest['conditions']}
    manifest['conditions']['charging_state'] = 'unplugged'
    for key in ('power', 'temperature'):
        manifest[key].update(instrument='synthetic fixture', method='synthetic arithmetic only',
                             calibration_or_accuracy='not real measurement', raw_source_reference='unit test')
    manifest['temperature']['surface_point'] = 'rear centre'
    raw = b't_seconds,power_w,surface_c,ambient_c\n0,2,30,20\n5,4,35,21\n10,6,40,22\n'
    return data, manifest, raw


class ExternalTests(unittest.TestCase):
    def test_integrates_actual_adjacent_values_not_fps_or_battery(self):
        d, p, s = fixture(); r = m.analyse(d, p, s)
        self.assertEqual(r['power']['energy_joules'], 40)
        self.assertEqual(r['power']['average_watts'], 4)
        self.assertEqual(r['power_coverage_fraction'], 1)
        self.assertEqual(r['temperature']['max_surface_above_ambient_c'], 18)
        self.assertIsNone(r['displayed_frames']['energy_per_displayed_frame_joules'])
        self.assertIn('UNVERIFIED', r['energy_benefit'])
    def test_overlapping_exclusions_merge_and_clip_linear_power(self):
        d, p, s = fixture(); d['exclusions'] = [{'start': 2, 'end': 4}, {'start': 3, 'end': 6}]
        r = m.analyse(d, p, s)
        self.assertEqual(r['included_seconds'], 6)
        self.assertAlmostEqual(r['power']['energy_joules'], 25.6)
        self.assertEqual([x['t'] for x in r['temperature']['included_samples']], [0, 10])
    def test_uncertainty_trims_start_end_and_expands_exclusions(self):
        d, p, s = fixture(); p['clock_uncertainty_seconds'] = .5
        d['exclusions'] = [{'start': 3, 'end': 4}]
        r = m.analyse(d, p, s)
        self.assertEqual(r['included_intervals_seconds'], [[.5, 2.5], [4.5, 9.5]])
        self.assertEqual(r['included_seconds'], 7)
    def test_external_clock_offset_has_explicit_sign(self):
        d, p, s = fixture(); p['clock_offset_seconds'] = 100
        s = s.replace(b'\n0,', b'\n-100,').replace(b'\n5,', b'\n-95,').replace(b'\n10,', b'\n-90,')
        self.assertEqual(m.analyse(d, p, s)['power']['energy_joules'], 40)
    def test_no_extrapolation_before_after_available_samples(self):
        d, p, _ = fixture(); s = b't_seconds,power_w,surface_c,ambient_c\n2,4,,\n7,4,,\n'
        r = m.analyse(d, p, s)
        self.assertEqual(r['power']['energy_joules'], 20)
        self.assertEqual(r['power_coverage_fraction'], .5)
    def test_missing_power_breaks_both_adjacent_segments(self):
        d, p, s = fixture(); s = s.replace(b'5,4,', b'5,,')
        r = m.analyse(d, p, s)
        self.assertIsNone(r['power']['energy_joules']); self.assertEqual(r['power_covered_seconds'], 0)
        self.assertEqual(r['temperature']['max_surface_c'], 40)
    def test_gaps_are_not_silently_integrated(self):
        d, p, s = fixture(); p['max_gap_seconds'] = 4
        r = m.analyse(d, p, s); self.assertEqual(r['skipped_oversized_gaps'], 2)
        self.assertIsNone(r['power']['average_watts'])
    def test_identity_mismatch_rejected(self):
        for key in ('session_id', 'build_sha', 'device_identifier'):
            d, p, s = fixture(); p['identity'][key] = 'other'
            with self.assertRaisesRegex(ValueError, 'identity'): m.analyse(d, p, s)
    def test_template_is_incomplete_cannot_be_used_as_measured_data(self):
        d, _, s = fixture()
        with self.assertRaises(ValueError): m.analyse(d, m.template(d), s)
    def test_power_requires_supported_units_quantity_and_provenance(self):
        for key, value in [('units', 'mW'), ('quantity', 'usb_c_supplied_power'), ('instrument', ''), ('raw_source_reference', None)]:
            d, p, s = fixture(); p['power'][key] = value
            with self.assertRaises(ValueError): m.analyse(d, p, s)
    def test_charging_power_rejected_but_charging_surface_data_allowed(self):
        d, p, s = fixture(); p['conditions']['charging_state'] = 'charging'
        with self.assertRaisesRegex(ValueError, 'unplugged'): m.analyse(d, p, s)
        p['power'] = None; s = s.replace(b',2,', b',,').replace(b',4,', b',,').replace(b',6,', b',,')
        r = m.analyse(d, p, s); self.assertEqual(r['temperature']['max_surface_c'], 40)
        self.assertIsNone(r['power']['average_watts'])
    def test_exported_charging_sample_cannot_be_overridden_by_manifest(self):
        d, p, s = fixture(); d['samples'] = [{'t': 5, 'battery_state': 2}]
        with self.assertRaisesRegex(ValueError, 'contradicts'): m.analyse(d, p, s)
        d['exclusions'] = [{'start': 4, 'end': 6}]
        self.assertEqual(m.analyse(d, p, s)['power_covered_seconds'], 8)
    def test_nonfinite_negative_and_duplicate_times_rejected(self):
        for changed in [b'5,nan,35,21', b'5,-1,35,21', b'0,4,35,21', b'5,inf,35,21', b'5,4,-274,21']:
            d, p, s = fixture(); s = s.replace(b'5,4,35,21', changed)
            with self.assertRaises(ValueError): m.analyse(d, p, s)
    def test_malformed_csv_and_duplicate_header_rejected(self):
        for raw in [b't_seconds,power_w,surface_c,ambient_c\n0,2\n', b't_seconds,power_w,power_w,ambient_c\n0,2,3,4\n']:
            d, p, _ = fixture()
            with self.assertRaises(ValueError): m.analyse(d, p, raw)
    def test_json_duplicates_nonfinite_boolean_and_wrong_schema_rejected(self):
        for raw in ['{"x":1,"x":2}', '{"x":NaN}']:
            with self.assertRaises(ValueError): m.read_json(raw)
        d, p, s = fixture(); p['clock_uncertainty_seconds'] = True
        with self.assertRaises(ValueError): m.analyse(d, p, s)
        d, p, s = fixture(); d['schema_version'] = 999
        with self.assertRaises(ValueError): m.analyse(d, p, s)
    def test_bad_exclusion_and_impossible_alignment_are_not_zero_cost(self):
        for row in [{'start': 6, 'end': 4}, {'start': -1, 'end': 2}, {'start': 1, 'end': 11}]:
            d, p, s = fixture(); d['exclusions'] = [row]
            with self.assertRaises(ValueError): m.analyse(d, p, s)
        d, p, s = fixture(); p['clock_uncertainty_seconds'] = 6
        r = m.analyse(d, p, s); self.assertEqual(r['included_seconds'], 0)
        self.assertIsNone(r['power']['energy_joules'])
    def frames(self):
        d, p, s = fixture()
        p['displayed_frames'] = {'quantity': 'actually_displayed_frames', 'complete': True, 'dropped_records': 0,
                                'instrument': 'synthetic display counter', 'method': 'unit test',
                                'raw_source_reference': 'fixture', 'coverage_seconds': [[0, 10]]}
        frames = b't_seconds\n' + b''.join(f'{i}\n'.encode() for i in range(11))
        return d, p, s, frames
    def test_display_denominator_requires_actual_complete_aligned_external_stream(self):
        d, p, s, f = self.frames(); r = m.analyse(d, p, s, f)
        self.assertEqual(r['displayed_frames']['count_over_energy_intervals'], 10)
        self.assertEqual(r['displayed_frames']['energy_per_displayed_frame_joules'], 4)
        d['exclusions'] = [{'start': 3, 'end': 7}]
        r = m.analyse(d, p, s, f); self.assertEqual(r['displayed_frames']['count_over_energy_intervals'], 6)
        self.assertEqual(r['power_covered_seconds'], 6)
    def test_partial_display_coverage_and_drops_do_not_fabricate_denominator(self):
        d, p, s, _ = self.frames(); p['displayed_frames']['coverage_seconds'] = [[0, 5]]
        r = m.analyse(d, p, s, b't_seconds\n1\n2\n')
        self.assertIsNone(r['displayed_frames']['energy_per_displayed_frame_joules'])
        p['displayed_frames']['dropped_records'] = 1
        with self.assertRaises(ValueError): m.analyse(d, p, s, b't_seconds\n1\n')
    def test_host_cap_and_estimated_feedback_are_not_display_measurements(self):
        d, p, s, f = self.frames(); p['displayed_frames']['quantity'] = 'host_present_calls'
        with self.assertRaises(ValueError): m.analyse(d, p, s, f)
    def test_display_duplicate_timestamp_and_outside_coverage_rejected(self):
        for raw in [b't_seconds\n1\n1\n', b't_seconds\n11\n', b't_seconds\nnan\n']:
            d, p, s, _ = self.frames()
            with self.assertRaises(ValueError): m.analyse(d, p, s, raw)
    def test_cli_writes_hashes_and_truthful_report_from_supplied_files(self):
        d, p, s = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'diagnostics.json').write_text(json.dumps(d))
            (root/'manifest.json').write_text(json.dumps(p)); (root/'samples.csv').write_bytes(s)
            subprocess.run([sys.executable, str(ROOT/'scripts/external_efficiency.py'), str(root/'diagnostics.json'),
                '--manifest', str(root/'manifest.json'), '--samples', str(root/'samples.csv'), '--output-prefix', str(root/'analysis')], check=True)
            r = json.loads((root/'analysis.json').read_text())
            self.assertEqual(r['inputs_sha256']['samples'], m.digest(s))
            self.assertIn('UNVERIFIED', (root/'analysis.md').read_text())
    def paired(self):
        d, p, samples = fixture()
        raw = json.dumps(d).encode(); result = m.analyse(d, p, samples)
        result['inputs_sha256'] = {'diagnostics': m.digest(raw)}
        return d, copy.deepcopy(d), result, copy.deepcopy(result), [m.digest(raw), m.digest(raw)]
    def test_external_pair_reports_difference_but_never_awards_gate(self):
        a, b, x, y, hashes = self.paired(); y['power']['average_watts'] = 3
        r = external_pair_audit(a, b, x, y, hashes)
        self.assertEqual(r['blockers'], [])
        self.assertEqual(r['candidate_minus_baseline']['average_watts_relative_change_percent'], -25)
        self.assertEqual(r['roadmap_gates_automatically_passed'], [])
        self.assertIn('UNVERIFIED', r['energy_improvement'])
    def test_external_pair_rejects_wrong_file_hash_and_identity(self):
        a, b, x, y, hashes = self.paired(); hashes[1] = 'other'
        r = external_pair_audit(a, b, x, y, hashes)
        self.assertTrue(any('hash' in z for z in r['blockers']))
        y['identity'] = {}; r = external_pair_audit(a, b, x, y, hashes)
        self.assertTrue(any('identity' in z for z in r['blockers']))
    def test_external_pair_rejects_partial_energy_coverage(self):
        a, b, x, y, hashes = self.paired(); y['power_coverage_fraction'] = .5
        r = external_pair_audit(a, b, x, y, hashes)
        self.assertTrue(any('99%' in z for z in r['blockers']))
    def test_external_pair_rejects_environment_or_surface_point_confounds(self):
        for mutate in [lambda y:y['conditions'].update(brightness='other'),
                       lambda y:y['provenance']['temperature'].update(surface_point='different'),
                       lambda y:y['conditions'].update(charging_state='charging')]:
            a, b, x, y, hashes = self.paired(); mutate(y)
            self.assertTrue(external_pair_audit(a, b, x, y, hashes)['blockers'])
    def test_external_pair_rejects_different_configuration_or_duration(self):
        a, b, x, y, hashes = self.paired(); y['configuration']['requested_fps'] = 30
        self.assertTrue(any('configuration' in z for z in external_pair_audit(a,b,x,y,hashes)['blockers']))
        a, b, x, y, hashes = self.paired(); y['power_covered_seconds'] = 5
        self.assertTrue(any('durations' in z for z in external_pair_audit(a,b,x,y,hashes)['blockers']))
    def test_external_pair_allows_different_raw_references_not_different_methods(self):
        a, b, x, y, hashes = self.paired(); y['provenance']['power']['raw_source_reference'] = 'candidate.trace'
        self.assertEqual(external_pair_audit(a,b,x,y,hashes)['blockers'], [])
        y['provenance']['power']['method'] = 'different instrument method'
        self.assertTrue(any('method' in z for z in external_pair_audit(a,b,x,y,hashes)['blockers']))
    def test_cli_external_pair_is_attached_and_raw_evidence_cannot_be_overwritten(self):
        a, b, x, y, hashes = self.paired(); b['metadata']['session_id'] = 'candidate'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for side, data, result in [('a', a, x), ('b', b, y)]:
                raw = json.dumps(data).encode(); (root/(side+'.json')).write_bytes(raw)
                result['identity'] = m.identity(data); result['inputs_sha256']['diagnostics'] = m.digest(raw)
                (root/(side+'-external.json')).write_text(json.dumps(result))
            command = [sys.executable, str(ROOT/'scripts/compare_efficiency.py'), str(root/'a.json'), str(root/'b.json'),
                       '--recipe', 'engine-only', '--external-baseline', str(root/'a-external.json'),
                       '--external-candidate', str(root/'b-external.json'), '--output', str(root/'result.json')]
            subprocess.run(command, check=True)
            r = json.loads((root/'result.json').read_text())
            self.assertEqual(r['external_measurements']['blockers'], [])
            self.assertEqual(r['status'], 'BLOCKED FOR CONTROLLED INFERENCE')  # Missing actual gameplay preflight stays blocked.
            original = (root/'a.json').read_bytes(); command[-1] = str(root/'a.json')
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual((root/'a.json').read_bytes(), original)
    def test_template_cannot_overwrite_original_export(self):
        d, p, s = fixture()
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory)/'diagnostics.json'; original = json.dumps(d); file.write_text(original)
            command = [sys.executable, str(ROOT/'scripts/external_efficiency.py'), str(file), '--template', str(file)]
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(file.read_text(), original)
    def test_size_limit_enforced_before_reading(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'too_large'
            with p.open('wb') as stream: stream.truncate(m.MAX_BYTES+1)
            with self.assertRaises(ValueError): m.load_bytes(p)


if __name__ == '__main__': unittest.main()
