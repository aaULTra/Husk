#!/usr/bin/env python3
"""Compile-contract identity changes only for relevant pinned inputs, not diagnostics."""
import importlib.util,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('prepare',ROOT/'scripts/prepare_spatial_driver.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ArchiveCompatibilityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'ExternalRevisions').mkdir();self.rev=self.root/'ExternalRevisions/SPIRV-Cross_repo_revision';self.rev.write_text('0'*40+'\n')
 def test_diagnostic_changes_do_not_force_new_native_archive_namespace(self):
  before,inputs=m.archive_compatibility_id(self.root)
  (self.root/'HuskSpatialBuild.json').write_text('{"diagnostic_patch":"changed"}')
  (self.root/'HuskDisplay.inc').write_text('changed presentation observation only')
  after,_=m.archive_compatibility_id(self.root)
  self.assertEqual(before,after);self.assertEqual(inputs['upstream_commit'],m.PIN);self.assertEqual(inputs['schema'],2)
 def test_spirv_cross_revision_changes_compatibility(self):
  before,_=m.archive_compatibility_id(self.root);self.rev.write_text('1'*40)
  self.assertNotEqual(before,m.archive_compatibility_id(self.root)[0])
 def test_upstream_pin_and_compiler_contract_each_change_compatibility(self):
  before,_=m.archive_compatibility_id(self.root)
  with patch.object(m,'PIN','different-driver'):self.assertNotEqual(before,m.archive_compatibility_id(self.root)[0])
  with patch.object(m,'NATIVE_COMPILER_CONTRACT','changed-native-semantics'):self.assertNotEqual(before,m.archive_compatibility_id(self.root)[0])
 def test_missing_revision_does_not_guess_compatible_namespace(self):
  self.rev.unlink()
  with self.assertRaises(FileNotFoundError):m.archive_compatibility_id(self.root)
 def test_empty_or_nonrevision_input_is_not_accepted_as_compatibility(self):
  for value in ['', 'not-a-revision', '0'*39, '0'*41]:
   self.rev.write_text(value)
   with self.assertRaises(ValueError):m.archive_compatibility_id(self.root)
if __name__=='__main__':unittest.main()
