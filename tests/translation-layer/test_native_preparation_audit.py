#!/usr/bin/env python3
"""Native receipts must reconcile with actual captures without inventing reuse or savings."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_native_preparation import audit_preparation,PIN
from test_comparison_campaign import run


def inputs():
    a=run();a['schema_version']=10
    a['metadata']['launch_configuration']['engine_only_limiter']=False
    a['metadata']['launch_configuration']['native_pipeline_archive_mode']=2
    build={'upstream_commit':PIN,'native_archive_abi':1,'husk_native_pipeline_patch_sha256':'a'*64}
    stats=dict(requested=True,supported=True,pending=2,prepared=0,prepare_calls=0,saved_bytes=0,prepare_ns=0,write_failures=0,read_failures=0,restored_bytes=0,archive_attachments=0)
    a['native_pipeline_archive']=copy.deepcopy(stats)
    a['spatial_upscaling']={'driver_build':build}
    b=copy.deepcopy(a);b['metadata']['session_id']='B'
    b['native_pipeline_archive'].update(pending=0,restored_bytes=12000,archive_attachments=4)
    receipt=dict(schema_version=1,type='paused_native_pipeline_preparation',result=1,
                 preceding_session_metadata={k:a['metadata'][k]for k in ['build_sha','device_identifier','os','session_id']},
                 build_sha=a['metadata']['build_sha'],configuration=copy.deepcopy(a['metadata']['launch_configuration']),
                 driver_build=copy.deepcopy(build),game_pause_requested=True,no_gpu_idle_wait=True,
                 measured_host_wall_seconds=.4,estimated_process_cpu_seconds=.6,
                 started_monotonic_seconds=1000.,ended_monotonic_seconds=1000.4,
                 before=copy.deepcopy(stats),after=copy.deepcopy(stats))
    receipt['after'].update(pending=0,prepared=2,prepare_calls=1,saved_bytes=12000,prepare_ns=300000000)
    return [a,receipt,b]


class PreparationAuditTests(unittest.TestCase):
    def setUp(self):self.items=inputs()
    def audit(self):return audit_preparation(*self.items)
    def test_valid_identity_cost_and_restore_still_never_proves_hits_energy_or_gates(self):
        result=self.audit();self.assertEqual(result['errors'],[])
        self.assertFalse(result['cache_hit_verified']);self.assertEqual(result['energy_improvement'],'UNVERIFIED')
        self.assertEqual(result['roadmap_gates_automatically_passed'],[]);self.assertIsNone(result['watts'])
        self.assertEqual(result['preparation']['process_cpu_seconds_estimated'],.6) # multithread CPU can exceed wall
    def test_inputs_are_immutable(self):
        saved=copy.deepcopy(self.items);self.audit();self.assertEqual(saved,self.items)
    def test_other_device_build_or_preceding_session_blocks(self):
        for key in ['device_identifier','build_sha','os','session_id']:
            with self.subTest(key=key):
                saved=self.items[1]['preceding_session_metadata'][key]
                self.items[1]['preceding_session_metadata'][key]='different';self.assertTrue(self.audit()['errors'])
                self.items[1]['preceding_session_metadata'][key]=saved
    def test_driver_pin_digest_and_launch_changes_block(self):
        for apply in [lambda x:x[1]['driver_build'].update(upstream_commit='other'),
                      lambda x:x[1]['driver_build'].update(husk_native_pipeline_patch_sha256='bad'),
                      lambda x:x[2]['metadata']['launch_configuration'].update(submission_mode=1)]:
            self.items=inputs();apply(self.items);self.assertTrue(self.audit()['errors'])
    def test_unsupported_failed_write_absent_restore_or_attachment_blocks(self):
        for apply in [lambda x:x[1].update(result=-1),lambda x:x[1]['after'].update(supported=False),
                      lambda x:x[1]['after'].update(saved_bytes=64*1024*1024+1),
                      lambda x:x[2]['native_pipeline_archive'].update(restored_bytes=0),
                      lambda x:x[2]['native_pipeline_archive'].update(archive_attachments=0)]:
            self.items=inputs();apply(self.items);self.assertTrue(self.audit()['errors'])
    def test_counts_endpoints_and_nonfinite_costs_cannot_be_accepted(self):
        for apply in [lambda x:x[1]['before'].update(pending=9),lambda x:x[1]['after'].update(prepared=3),
                      lambda x:x[1]['after'].update(prepare_calls=0),lambda x:x[1].update(ended_monotonic_seconds=1001),
                      lambda x:x[1].update(estimated_process_cpu_seconds=float('nan'))]:
            self.items=inputs();apply(self.items);self.assertTrue(self.audit()['errors'])
    def test_one_long_call_and_unavailable_cpu_are_disclosed_not_mistaken_for_power(self):
        self.items[1].update(measured_host_wall_seconds=3,ended_monotonic_seconds=1003,estimated_process_cpu_seconds=None)
        result=self.audit();self.assertFalse(result['errors']);self.assertTrue(any('uninterruptible' in s for s in result['warnings']))
        self.assertIsNone(result['preparation']['process_cpu_seconds_estimated'])
    def test_cli_preserves_raw_files_hashes_inputs_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory()as d:
            paths=[Path(d)/s for s in ['first.json','receipt.json','restart.json']]
            for p,x in zip(paths,self.items):p.write_text(json.dumps(x))
            output=Path(d)/'audit.json';cmd=[sys.executable,str(ROOT/'scripts/audit_native_preparation.py'),*map(str,paths)]
            subprocess.run(cmd+['--output',str(output)],check=True,capture_output=True)
            result=json.loads(output.read_text());self.assertEqual(len(result['inputs']),3)
            self.assertTrue(all(len(v['file_sha256'])==64 for v in result['inputs'].values()))
            before=paths[0].read_bytes();r=subprocess.run(cmd+['--output',str(paths[0])],capture_output=True)
            self.assertNotEqual(r.returncode,0);self.assertEqual(paths[0].read_bytes(),before)


if __name__=='__main__':unittest.main()
