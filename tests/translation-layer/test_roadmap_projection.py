#!/usr/bin/env python3
"""Conditional arithmetic does not award evidence or change the fixed roadmap."""
import copy
import json
import subprocess
import tempfile
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from roadmap_progress import project, score

class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.ledger=json.loads((ROOT/'docs/performance/progress/031d9d2698f2fbd0439547b2febd45a9c7c2e5b5.ledger.json').read_text())
        self.scenario=json.loads((ROOT/'docs/performance/progress/validate-50-v1.scenario.json').read_text())
    def test_fifty_path_uses21_existing_gates_without_changing_current_ledger(self):
        before=copy.deepcopy(self.ledger)
        result=project(self.ledger,self.scenario)
        self.assertAlmostEqual(result['actual_overall_percent'],26.27)
        self.assertAlmostEqual(result['conditional_overall_percent'],50.17)
        self.assertEqual(len(result['unearned_gate_ids']),21)
        self.assertEqual(before,self.ledger)
        self.assertFalse(result['ledger_modified'])
        self.assertIn('UNEARNED',result['status'])
    def test_unknown_duplicate_gates_and_changed_definitions_rejected(self):
        for change in ['unknown','duplicate','version']:
            s=copy.deepcopy(self.scenario)
            if change=='unknown':s['conditional_gate_ids'].append('M99-D1')
            if change=='duplicate':s['conditional_gate_ids'].append(s['conditional_gate_ids'][0])
            if change=='version':s['gate_version']='other'
            with self.assertRaises(ValueError):project(self.ledger,s)
    def test_no_assumptions_or_empty_scenario_rejected(self):
        for field in ['conditional_gate_ids','assumptions']:
            s=copy.deepcopy(self.scenario);s[field]=[]
            with self.assertRaises(ValueError):project(self.ledger,s)
    def test_previously_passed_gates_do_not_gain_double_credit(self):
        s=copy.deepcopy(self.scenario);s['conditional_gate_ids'].append('M1-I1')
        self.assertEqual(project(self.ledger,s)['conditional_overall_percent'],50.17)
        self.assertNotIn('M1-I1',project(self.ledger,s)['unearned_gate_ids'])
    def test_cli_refuses_to_overwrite_ledger_or_scenario(self):
        with tempfile.TemporaryDirectory() as directory:
            a=Path(directory)/'ledger.json';b=Path(directory)/'scenario.json'
            a.write_text(json.dumps(self.ledger));b.write_text(json.dumps(self.scenario))
            original=[a.read_bytes(),b.read_bytes()]
            for target in [a,b]:
                r=subprocess.run([sys.executable,str(ROOT/'scripts/roadmap_progress.py'),str(a),'--scenario',str(b),'--output',str(target)],capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0)
            self.assertEqual([a.read_bytes(),b.read_bytes()],original)
    def test_cli_projection_matches_saved_conditional_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'projection.json'
            subprocess.run([sys.executable,str(ROOT/'scripts/roadmap_progress.py'),str(ROOT/'docs/performance/progress/031d9d2698f2fbd0439547b2febd45a9c7c2e5b5.ledger.json'),'--scenario',str(ROOT/'docs/performance/progress/validate-50-v1.scenario.json'),'--output',str(out)],check=True)
            expected=json.loads((ROOT/'docs/performance/progress/validate-50-v1.projection.json').read_text())
            self.assertEqual(json.loads(out.read_text()),expected)
    def test_no_duo_or_shader_preparation_credit_and_fixed_weights_preserved(self):
        r=project(self.ledger,self.scenario)
        for key in ['M2','M5','M8','M10']:
            a=next(m for m in r['actual_milestones'] if m['id']==key)
            b=next(m for m in r['conditional_milestones'] if m['id']==key)
            self.assertEqual(a,b)
        self.assertEqual(sum(m['weight'] for m in r['conditional_milestones']),100)

if __name__=='__main__':unittest.main()
