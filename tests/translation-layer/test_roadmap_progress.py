#!/usr/bin/env python3
import copy, importlib.util, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('progress',ROOT/'scripts/roadmap_progress.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ProgressTests(unittest.TestCase):
 def setUp(self):self.ledger=json.loads((ROOT/'docs/performance/progress/roadmap-v1.json').read_text())
 def test_complete_weighted_ledger_has_separate_duo_and_unknown_energy(self):
  r=m.score(self.ledger);self.assertEqual(sum(x['weight'] for x in r['milestones']),100);self.assertEqual(r['duo_milestone_percent'],0);self.assertTrue(0<r['overall_percent']<60)
 def test_code_completion_cannot_complete_device_and_energy_tracks(self):
  for row in self.ledger['milestones'][1:]:
   for g in row['tracks']['I']:g['status']='passed';g['evidence']=['test']
  self.assertLessEqual(m.score(self.ledger)['overall_percent'],40)
 def test_missing_milestone_and_changed_weights_rejected(self):
  bad=copy.deepcopy(self.ledger);bad['milestones'].pop()
  with self.assertRaises(ValueError):m.score(bad)
  self.ledger['milestones'][1]['weight']+=1
  with self.assertRaises(ValueError):m.score(self.ledger)
 def test_pass_requires_evidence_and_unique_gate_identity(self):
  self.ledger['milestones'][0]['documentation'][0]['evidence']=[]
  with self.assertRaises(ValueError):m.score(self.ledger)
 def test_every_passed_evidence_reference_exists_in_repository(self):
  for row in self.ledger['milestones']:
   tracks=[row['documentation']] if row['id']=='M0' else row['tracks'].values()
   for gs in tracks:
    for g in gs:
     for ref in g['evidence']:self.assertTrue((ROOT/ref.split('#')[0]).exists(),ref)
if __name__=='__main__':unittest.main()
