#!/usr/bin/env python3
"""Paired evidence checks reject confounds and never manufacture an energy pass."""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from compare_efficiency import compare_pair, included_seconds, load_export, worker_treatment


def run():
    config = dict(engine='ue4', game='Dungeons', launch_width=2128, launch_height=1600,
                  sharp_graphics=True, efficient_graphics=True, requested_fps=60,
                  worker_policy=2, submission_mode=0, detailed_driver_profiling=False,
                  metalfx_spatial_requested=False, metalfx_input_percent=80, windowed=False,
                  engine_only_limiter=False, clock_correct_presentation=False,
                  pipeline_identification=False, pipeline_creation_feedback=False,
                  render_target_inventory=False)
    summary = dict(interval_count=18000, interval_seconds=300., host_cadence_fps=60.,
                   p95_ms=16.8, p99_ms=17., worst_ms=25., above_20_ms=20,
                   above_33_333333_ms=0, above_50_ms=0, slow_pipeline_calls=1,
                   worst_pipeline_ns=20_000_000, frame_distribution_complete=True)
    return dict(schema_version=9, duration_seconds=300., summary=summary,
                metadata=dict(build_sha='same-source-dirty', device_identifier='iPad16,5', os='27.2',
                              session_id='A', launch_configuration=config, cpu_thread_sampling_requested=False),
                gpu_sampling=dict(requested=False), samples=[dict(t=1., excluded=False,
                    cpu_sample_elapsed_seconds=2., process_cpu_percent_one_core=60.,
                    battery_state=1, environment=dict(brightness=.5, low_power_mode=False)),
                    dict(t=299., excluded=False, battery_state=1, environment=dict(brightness=.5, low_power_mode=False))],
                exclusions=[], windows=[], worker_policy={})


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.a = run()
        self.b = copy.deepcopy(self.a)
        self.b['metadata']['session_id'] = 'B'
        self.b['metadata']['launch_configuration']['engine_only_limiter'] = True

    def compare(self, recipe='engine-only'):
        return compare_pair(self.a, self.b, recipe)

    def test_matching_pair_is_only_metadata_ready_and_never_energy_or_gate_acceptance(self):
        result = self.compare()
        self.assertEqual(result['blockers'], [])
        self.assertEqual(result['roadmap_gates_automatically_passed'], [])
        self.assertEqual(result['energy_improvement'], 'UNVERIFIED')
        self.assertIsNone(result['power_watts'])
        self.assertIsNone(result['displayed_frames'])
        self.assertTrue(result['unrecorded_context'])
        self.assertTrue(result['detailed_diagnostics_off_both'])

    def test_inputs_not_modified_and_one_control_difference(self):
        before = copy.deepcopy([self.a, self.b])
        self.assertEqual(self.compare()['changed_launch_fields'], ['engine_only_limiter'])
        self.assertEqual([self.a, self.b], before)

    def test_native_archive_pair_needs_same_driver_and_actual_restore_attachment(self):
        self.b['metadata']['launch_configuration']['engine_only_limiter'] = False
        for d, mode in [(self.a, 1), (self.b, 2)]:
            d['metadata']['launch_configuration']['native_pipeline_archive_mode'] = mode
            d['spatial_upscaling'] = {'driver_build': {'native_archive_abi': 1, 'patch': 'same'}}
        self.assertTrue(self.compare('native-archive')['blockers'])
        self.b['native_pipeline_archive'] = dict(requested=True, supported=True, restored_bytes=12000, archive_attachments=4)
        self.assertEqual(self.compare('native-archive')['blockers'], [])
        self.b['spatial_upscaling']['driver_build']['patch'] = 'different'
        self.assertTrue(any('manifest' in x for x in self.compare('native-archive')['blockers']))

    def test_feedback_clock_pair_needs_independent_runtime_treatment_and_observation(self):
        self.b['metadata']['launch_configuration']['engine_only_limiter'] = False
        self.a['metadata']['launch_configuration']['feedback_clock_correction'] = False
        self.b['metadata']['launch_configuration']['feedback_clock_correction'] = True
        self.assertTrue(self.compare('feedback-clock')['blockers'])
        self.b['presentation_clock'] = dict(feedback_only_requested=True, requested=False, feedback_records=20)
        self.assertEqual(self.compare('feedback-clock')['blockers'], [])
        self.b['presentation_clock']['invalid_clock_or_overflow'] = 1
        self.assertTrue(self.compare('feedback-clock')['blockers'])

    def test_build_device_os_duplicate_and_missing_identity_block(self):
        for key, value in [('build_sha', 'other'), ('device_identifier', 'phone'), ('os', '28'), ('session_id', 'A'), ('build_sha', 'UNAVAILABLE')]:
            with self.subTest(key=key, value=value):
                old = self.b['metadata'][key]
                self.b['metadata'][key] = value
                self.assertTrue(self.compare()['blockers'])
                self.b['metadata'][key] = old

    def test_extra_changed_controls_and_unrelated_shared_experiments_block(self):
        self.b['metadata']['launch_configuration']['submission_mode'] = 1
        self.assertTrue(any('Additional changed control' in x for x in self.compare()['blockers']))
        self.a['metadata']['launch_configuration']['submission_mode'] = 1
        self.assertTrue(any('unrelated experimental' in x for x in self.compare()['blockers']))

    def test_changed_gpu_and_thread_sampling_block(self):
        self.b['gpu_sampling']['requested'] = True
        self.assertIn('Changed diagnostic: gpu_sampling.requested', self.compare()['blockers'])
        self.b['metadata']['cpu_thread_sampling_requested'] = True
        self.assertTrue(any('cpu_thread_sampling' in x for x in self.compare()['blockers']))

    def test_brightness_charging_lpm_and_frame_loss_block(self):
        self.b['samples'][0]['environment'].update(brightness=.8, low_power_mode=True)
        self.b['samples'][0]['battery_state'] = 2
        self.b['summary']['dropped_frame_intervals_cumulative'] = 1
        result = self.compare()
        for needle in ['Brightness', 'unplugged', 'Low Power', 'incomplete host-frame']:
            self.assertTrue(any(needle in x for x in result['blockers']), result['blockers'])

    def test_overlapping_exclusions_are_unioned_and_bad_bounds_are_not_used(self):
        self.a['exclusions'] = [dict(start=10., end=20.), dict(start=15., end=25.)]
        self.assertEqual(included_seconds(self.a), 285.)
        self.a['exclusions'].append(dict(start=-1., end=2.))
        self.assertIsNone(included_seconds(self.a))
        self.assertTrue(any('exclusions/duration' in x for x in self.compare()['blockers']))

    def test_mismatched_duration_and_missing_reference_configuration_block(self):
        self.b['duration_seconds'] = 500.
        del self.b['metadata']['launch_configuration']['launch_width']
        result = self.compare()
        self.assertTrue(any('durations differ' in x for x in result['blockers']))
        self.assertTrue(any('Missing launch configuration' in x for x in result['blockers']))

    def test_rates_use_retained_intervals_not_requested_fps_and_cpu_is_not_power(self):
        self.b['summary'].update(interval_count=15000, host_cadence_fps=50.)
        result = self.compare()
        self.assertAlmostEqual(result['candidate']['over20_per1000_host_intervals'], 20/15)
        self.assertEqual(result['candidate_minus_baseline']['retained_fps'], -10.)
        self.assertEqual(result['candidate']['cpu_weighted_percent_one_core'], 60.)
        self.assertIsNone(result['power_watts'])

    def worker_pair(self, mode):
        self.b['metadata']['launch_configuration'].update(engine_only_limiter=False, worker_policy=mode)
        row = dict(observed_t=100., role=1, mode=mode, after_qos=0x11, set_result=0, query_result=0)
        self.b['worker_policy'] = dict(admissions_since_launch=10, last_observed_workers=[row])
        self.b['samples'][0]['worker_controller'] = dict(trial_requested=True, admissions_since_launch=9)
        self.b['samples'][1]['worker_controller'] = dict(trial_requested=True, admissions_since_launch=10)
        return row

    def test_strict_worker_needs_local_treatment_not_lifetime_counts(self):
        row = self.worker_pair(3)
        self.assertEqual(self.compare('strict-worker')['blockers'], [])
        row['observed_t'] = -1
        result = self.compare('strict-worker')
        self.assertTrue(any('treatment evidence' in x for x in result['blockers']))
        self.assertEqual(result['worker_treatment']['included_admission_counter_increase'], 1)

    def test_excluded_caps_are_not_treatment_and_relative_is_not_strict(self):
        self.worker_pair(4)
        result = self.compare('relative-worker')
        self.assertTrue(any('cannot pass strict' in x for x in result['warnings']))
        self.b['exclusions'] = [dict(start=99., end=101.)]
        self.assertEqual(worker_treatment(self.b, 4)['included_normal_utility_observations'], 0)

    def test_spatial_requires_real_scaler_evidence_and_preserved_output(self):
        self.b['metadata']['launch_configuration'].update(engine_only_limiter=False, metalfx_spatial_requested=True)
        self.assertTrue(self.compare('spatial')['blockers'])
        self.b['spatial_upscaling'] = dict(configured=True, encoded_calls=100, failures=0, output_width=2128, output_height=1600)
        result = self.compare('spatial')
        self.assertEqual(result['blockers'], [])
        self.assertEqual(result['roadmap_gates_automatically_passed'], [])
        self.b['spatial_upscaling']['failures'] = 1
        self.assertTrue(self.compare('spatial')['blockers'])

    def test_external_context_is_preserved_as_user_supplied_and_missing_is_explicit(self):
        result = compare_pair(self.a, self.b, 'engine-only', {'baseline': {'route': 'camp'}, 'candidate': {'route': 'mission'}})
        self.assertTrue(any('route' in x for x in result['warnings']))
        self.assertIn('ambient_c', result['unrecorded_context'])
        self.assertIn('not independently', result['context_provenance'])

    def test_gzip_and_plain_provenance_hashes_preserve_same_decoded_data(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            encoded = json.dumps(self.a).encode()
            (p/'run.json').write_bytes(encoded)
            (p/'run.json.gz').write_bytes(gzip.compress(encoded))
            plain, a = load_export(p/'run.json')
            zipped, b = load_export(p/'run.json.gz')
            self.assertEqual(plain, zipped)
            self.assertEqual(a['decoded_sha256'], b['decoded_sha256'])
            self.assertNotEqual(a['file_sha256'], b['file_sha256'])

    def test_other_devices_and_games_do_not_inherit_m4_acceptance(self):
        for data in [self.a,self.b]:
            data['metadata']['device_identifier']='future-phone'
            data['metadata']['launch_configuration']['engine']='unity'
        result=self.compare()
        self.assertTrue(any('independent profile' in x for x in result['blockers']))
        self.assertTrue(any('Dungeons UE4' in x for x in result['blockers']))

    def test_missing_diagnostic_state_is_unknown_not_clean_off(self):
        for data in [self.a,self.b]:del data['gpu_sampling']['requested']
        result=self.compare()
        self.assertFalse(result['detailed_diagnostics_off_both'])
        self.assertTrue(any('activation is unknown' in x for x in result['warnings']))

    def test_non_finite_json_and_oversized_decompression_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'run.json'
            p.write_text('{"value": NaN}')
            with self.assertRaises(ValueError):load_export(p)
            p=Path(directory)/'run.json.gz'
            p.write_bytes(gzip.compress(b' '*1024))
            with patch('compare_efficiency.MAX_BYTES',128):
                with self.assertRaises(ValueError):load_export(p)

    def test_historical_e006_pair_is_not_accepted_as_controlled_energy_benefit(self):
        a, _ = load_export(ROOT/'docs/performance/runs/E-M4-006B.diagnostics.json.gz')
        b, _ = load_export(ROOT/'docs/performance/runs/E-M4-006A.diagnostics.json.gz')
        result = compare_pair(a, b, 'spatial')
        self.assertTrue(any('durations differ' in x for x in result['blockers']))
        self.assertFalse(result['detailed_diagnostics_off_both'])
        self.assertEqual(result['energy_improvement'], 'UNVERIFIED')


if __name__ == '__main__':
    unittest.main()
