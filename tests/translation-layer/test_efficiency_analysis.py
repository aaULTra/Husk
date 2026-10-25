#!/usr/bin/env python3
"""Independent arithmetic and uncertainty checks against archived device exports."""
import copy, importlib.util, json, unittest
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
if __name__=='__main__':unittest.main()
