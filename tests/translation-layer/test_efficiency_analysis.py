#!/usr/bin/env python3
"""Independent arithmetic and uncertainty checks against archived device exports."""
import copy, gzip, importlib.util, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('analysis',ROOT/'scripts/analyse_efficiency.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class AnalysisTests(unittest.TestCase):
 def test_archived_device_exports_reconcile_without_claiming_energy_benefit(self):
  for name in ['E-M4-003','E-M4-004']:
   a=m.audit(json.loads((ROOT/'docs/performance/runs'/f'{name}.diagnostics.json').read_text()))
   self.assertEqual(a['errors'],[]);self.assertTrue(a['energy_benefit'].startswith('UNVERIFIED'));self.assertTrue(a['gpu']['status'].startswith('UNAVAILABLE'))
 def test_overlap_and_sample_clipping_are_not_summed(self):
  def row(a,b):return dict(gpu_start_media_seconds=a,gpu_end_media_seconds=b,sample_start_media_seconds=100,sample_end_media_seconds=101)
  self.assertAlmostEqual(m.interval_union([row(99,100.5),row(100.3,102)]),1)
 def test_modified_window_is_detected(self):
  d=json.loads((ROOT/'docs/performance/runs/E-M4-004.diagnostics.json').read_text());d['windows'][0]['interval_count']+=1
  self.assertIn('Window/summary mismatch: interval_count',m.audit(d)['errors'])
 def test_adaptive_selection_is_not_admission_or_core_placement(self):
  d={'schema_version':4,'worker_policy':{'active_mode':3,'admissions_since_launch':0,'waiting_reason':'frame cadence'}}
  a=m.audit(d);self.assertIn('no admitted trial',a['warnings'][0]);self.assertEqual(a['worker']['core_residency'],'UNAVAILABLE')
 def test_metadata_differences_and_matching_conditions_still_do_not_prove_improvement(self):
  a=m.audit({'schema_version':4,'metadata':{'launch_configuration':{'worker_policy':2}}});b=copy.deepcopy(a);b['configuration']['worker_policy']=3
  c=m.compare(a,b);self.assertEqual(c['changed_fields'],['configuration.worker_policy']);self.assertEqual(c['energy_improvement'],'UNVERIFIED')
 def test_stage_library_hits_do_not_become_full_pipeline_or_energy_claims(self):
  d={'schema_version':5,'pipeline_groups_since_launch':[{'signature_version':'partial-v2','first_pipeline_application_hit_calls':0,'first_pipeline_valid_stage_feedback_count':2,'first_pipeline_stage_application_cache_hit_count':2}], 'pipeline_feedback_request':{'active':True,'enabled_devices':1}}
  a=m.audit(d);self.assertEqual(a['pipeline_groups_since_launch_top8'][0]['first_pipeline_stage_application_cache_hit_count'],2);self.assertTrue(a['energy_benefit'].startswith('UNVERIFIED'))
 def test_unknown_schema_is_not_silently_reinterpreted(self):
  with self.assertRaises(ValueError):m.audit({'schema_version':999})
 def test_gpu_exclusions_use_clock_mapping_and_union_not_summed_overlaps(self):
  def row(a,b):return dict(gpu_start_media_seconds=a,gpu_end_media_seconds=b,sample_start_media_seconds=100,sample_end_media_seconds=103)
  d={'metadata':{'monotonic_origin_seconds':1000,'gpu_clock_alignment':{'monotonic_anchor_seconds':1000,'media_anchor_seconds':100}},'gpu_records':[row(100,102),row(101,103)],'exclusions':[{'start':.5,'end':1.5},{'start':1,'end':2}]}
  a=m.gpu_exclusion_audit(d);self.assertEqual(a['records_overlapping_exclusions'],2);self.assertAlmostEqual(a['included_interval_union_seconds_estimated'],1.5);self.assertTrue(a['status'].startswith('ESTIMATED'));self.assertEqual(len(d['gpu_records']),2)
 def test_missing_or_nonfinite_clock_mapping_is_unavailable(self):
  a=m.gpu_exclusion_audit({});self.assertIsNone(a['included_interval_union_seconds_estimated']);self.assertTrue(a['status'].startswith('UNAVAILABLE'))
  d={'metadata':{'monotonic_origin_seconds':1,'gpu_clock_alignment':{'monotonic_anchor_seconds':float('inf'),'media_anchor_seconds':1}}};self.assertIsNone(m.gpu_exclusion_audit(d)['records_overlapping_exclusions'])
 def test_render_inventory_losses_do_not_become_absent_scene_or_energy_evidence(self):
  a=m.audit({'schema_version':6,'render_inventory':{'active':True,'dropped_observations':10,'groups_since_launch':[]}})
  self.assertTrue(any('absent sizes' in w for w in a['warnings']));self.assertTrue(any('diagnostic observation work' in w for w in a['warnings']));self.assertTrue(a['energy_benefit'].startswith('UNVERIFIED'))
 def test_metalfx_exports_preserve_raw_records_and_detect_boundary_overlap(self):
  for label,overlaps in [('A',3),('B',0)]:
   d=json.loads(gzip.decompress((ROOT/'docs/performance/runs'/f'E-M4-005{label}.diagnostics.json.gz').read_bytes()));a=m.audit(d)
   self.assertEqual(a['errors'],[]);self.assertTrue(a['spatial_upscaling']['configured']);self.assertEqual(a['spatial_upscaling']['failures'],0)
   self.assertEqual(a['gpu']['exclusion_audit']['records_overlapping_exclusions'],overlaps);self.assertIsNone(a['battery']['coarse_pp_per_hour']);self.assertTrue(a['energy_benefit'].startswith('UNVERIFIED'))
 def test_direct_gpu_brackets_override_anchor_and_work_without_one(self):
  row=dict(gpu_start_media_seconds=100,gpu_end_media_seconds=103,sample_start_media_seconds=100,sample_end_media_seconds=103)
  exclusion=dict(start=1000,end=2000,gpu_media_start_before_seconds=100.5,gpu_media_start_after_seconds=100.6,gpu_media_end_before_seconds=101.4,gpu_media_end_after_seconds=101.5)
  d={'schema_version':7,'gpu_records':[row],'exclusions':[exclusion]}
  a=m.gpu_exclusion_audit(d);self.assertAlmostEqual(a['included_interval_union_seconds_estimated'],2);self.assertEqual(a['direct_exclusion_count'],1);self.assertAlmostEqual(a['direct_boundary_uncertainty_seconds'],.2)
  d['metadata']={'monotonic_origin_seconds':1,'gpu_clock_alignment':{'monotonic_anchor_seconds':3,'media_anchor_seconds':4}}
  self.assertEqual(m.gpu_exclusion_audit(d)['included_interval_union_seconds_estimated'],2);self.assertEqual(m.audit(d)['errors'],[])
 def test_malformed_exclusion_cannot_silently_count_as_gameplay(self):
  d={'exclusions':[{'gpu_media_start_before_seconds':10,'gpu_media_start_after_seconds':9,'gpu_media_end_before_seconds':11,'gpu_media_end_after_seconds':12}]}
  self.assertTrue(m.gpu_exclusion_audit(d)['status'].startswith('UNAVAILABLE'))
 def test_end_anchor_exposes_clock_offset_change_without_correcting_raw_rows(self):
  d={'metadata':{'monotonic_origin_seconds':1000,'gpu_clock_alignment':{'monotonic_anchor_seconds':1000,'media_anchor_seconds':100},'gpu_clock_alignment_end':{'monotonic_anchor_seconds':1100.01,'media_anchor_seconds':200}}}
  self.assertAlmostEqual(m.gpu_exclusion_audit(d)['clock_offset_change_seconds'],.01)
if __name__=='__main__':unittest.main()

