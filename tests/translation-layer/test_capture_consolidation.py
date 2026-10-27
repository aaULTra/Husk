#!/usr/bin/env python3
"""Actual Swift bounded retention/share code and version-aware GPU loss arithmetic."""
from pathlib import Path
import copy
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from test_lifecycle_resilience import function

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'src/app/Husk'
spec=importlib.util.spec_from_file_location('capture_analysis',ROOT/'scripts/analyse_efficiency.py')
analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)

class AnalysisTests(unittest.TestCase):
 def test_schema14_prefix_recent_and_true_omissions_reconcile_without_double_counting(self):
  d=json.loads((ROOT/'docs/performance/runs/E-M4-004.diagnostics.json').read_text());d['schema_version']=14
  def row(a,b):return dict(gpu_start_media_seconds=a,gpu_end_media_seconds=b,sample_start_media_seconds=a,sample_end_media_seconds=b)
  d['gpu_records']=[row(100,101)];d['gpu_recent_records']=[row(200,201)]
  d['gpu_sampling']={'valid_records':3,'dropped_export_records':1,'observed_interval_union_seconds':2}
  r=analysis.audit(d);self.assertEqual(r['errors'],[]);self.assertEqual(r['gpu']['records'],2);self.assertEqual(r['gpu']['recent_records'],1)
  self.assertEqual(r['gpu']['sample_clipped_interval_union_seconds'],2);self.assertTrue(r['energy_benefit'].startswith('UNVERIFIED'))
  d['gpu_sampling']['dropped_export_records']=2;self.assertTrue(analysis.audit(d)['errors'])

@unittest.skipUnless(shutil.which('swiftc'),'Swift unavailable; required Apple IPA CI runs actual Swift')
class SwiftTests(unittest.TestCase):
 def compile_run(self,main,sources=()):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory);(p/'main.swift').write_text(main)
   subprocess.run(['swiftc',*[str(s)for s in sources],str(p/'main.swift'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True,timeout=20)
 def test_actual_history_retains_disjoint_early_recent_chronological_data_and_loss_counts(self):
  self.compile_run('''import Foundation
var h=BoundedRecordHistory<Int>(firstLimit:2,recentLimit:3)
for i in 0..<20 {h.append(i)}
precondition(h.first == [0,1] && h.recent == [17,18,19])
precondition(h.observed==20 && h.retained==5 && h.omitted==15)
for i in 20..<100000 {h.append(i)}
precondition(h.first == [0,1] && h.recent == [99997,99998,99999] && h.retained==5 && h.omitted==99995)
var prefix=BoundedRecordHistory<Int>(firstLimit:2,recentLimit:0)
for i in 0..<5 {prefix.append(i)}
precondition(prefix.first == [0,1] && prefix.recent.isEmpty && prefix.omitted==3)
var tail=BoundedRecordHistory<Int>(firstLimit:0,recentLimit:2)
for i in 0..<5 {tail.append(i)}
precondition(tail.first.isEmpty && tail.recent == [3,4] && tail.omitted==3)
h=BoundedRecordHistory(firstLimit:2,recentLimit:3)
precondition(h.observed==0 && h.omitted==0 && h.first.isEmpty && h.recent.isEmpty)
''',[APP/'BoundedRecordHistory.swift'])
 def test_actual_share_refreshes_native_state_and_preserves_prior_action_as_history(self):
  method=function((APP/'EfficiencyDiagnostics.swift').read_text(),'func exportNativeArchiveInspection()')
  # Inject a temporary filesystem and device facade; run the actual export body.
  self.compile_run(r'''
import Foundation
struct FileManager {
 static let `default`=FileManager()
 static let root=Foundation.FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
 func urls(for directory:Foundation.FileManager.SearchPathDirectory,in domain:Foundation.FileManager.SearchPathDomainMask)->[URL]{[Self.root]}
 func createDirectory(at url:URL,withIntermediateDirectories:Bool)throws{try Foundation.FileManager.default.createDirectory(at:url,withIntermediateDirectories:withIntermediateDirectories)}
}
struct UIDevice {static let current=UIDevice();let systemVersion="fixture"}
enum EfficiencyDeviceInventory {static func snapshot()->[String:Any]{[:]} }
enum EfficiencyMath {static func json(_ r:[String:Any])throws->Data{try JSONSerialization.data(withJSONObject:r,options:[.sortedKeys])} }
class Exporter {
 var archiveInspectionFiles:[URL]=[]
 var lastArchiveInspection:[String:Any]?=["action":"prepare_started","pending":8,"observed_monotonic_seconds":100]
 var archiveMessage=""
 let attached:[String:Any]=[:]
 var refreshes=0
 func archiveInspection()->(Int,Int,String){refreshes+=1;return (0,1,"empty")}
 func recordArchiveInspection(action:String,stats:Int,control:Int,status:String){lastArchiveInspection=["action":action,"pending":stats,"status_code":status,"observed_monotonic_seconds":110]}
 func nativeArchiveReport()->[String:Any]{["pending":0,"prepared":8]}
 func spatialReport()->[String:Any]{[:]} 
 /* ACTUAL */
}
let exporter=Exporter();exporter.exportNativeArchiveInspection()
precondition(exporter.refreshes==1 && exporter.archiveInspectionFiles.count==1)
let file=exporter.archiveInspectionFiles[0]
let root=try JSONSerialization.jsonObject(with:Data(contentsOf:file)) as! [String:Any]
let current=root["inspection"] as! [String:Any],previous=root["previous_user_inspection"] as! [String:Any]
precondition(current["action"] as? String == "share_inspection" && current["pending"] as? Int == 0)
precondition(previous["action"] as? String == "prepare_started" && previous["pending"] as? Int == 8)
precondition((root["native_pipeline_archive"] as! [String:Any])["prepared"] as? Int == 8)
exporter.exportNativeArchiveInspection();precondition(exporter.refreshes==2)
try Foundation.FileManager.default.removeItem(at:FileManager.root)
'''.replace('/* ACTUAL */',method))

if __name__=='__main__':unittest.main()
