#!/usr/bin/env python3
"""Real Foundation profile/report storage; no invented device or MetricKit delivery."""
import subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class DeviceProfileTests(unittest.TestCase):
 @unittest.skipUnless(sys.platform=='darwin','Apple Swift/Foundation check runs in IPA CI')
 def test_actual_store_device_game_validation_bounds_profiles_and_owned_report_rotation(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);(p/'main.swift').write_text(r'''
import Foundation
let root=URL(fileURLWithPath:CommandLine.arguments[1])
let store=EfficiencyProfileStore(directory:root.appendingPathComponent("profiles"))
let controls=EfficiencyProfile.Controls(graphics:"efficientHigh",orientation:"landscape",window:"fullScreen",resolution:0,customPercent:80,fps:60,worker:2,submission:0,spatial:false,spatialPercent:80,archive:0,archiveVerification:false,engineOnly:false,clockTimed:false,clockFeedback:false)
let first=EfficiencyProfile(name:"Reference controls",device:"iPad16,5",game:"Dungeons",build:"test-build",controls:controls)
let url=try store.save(first,device:"iPad16,5");let decoded=try store.decode(url:url,device:"iPad16,5")
assert(decoded.id==first.id&&decoded.controls==controls&&decoded.validation=="UNVERIFIED_LOCAL_EXPERIMENT")
assert(store.load(device:"iPad16,5",game:"Dungeons").count==1&&store.load(device:"other").isEmpty&&store.load(device:"iPad16,5",game:"Other").isEmpty)
func reject(_ p:EfficiencyProfile,device:String="iPad16,5",game:String="Dungeons"){do{_=try p.validated(for:device,game:game);fatalError("accepted invalid profile")}catch{}}
reject(first,device:"future-device");reject(first,game:"other-game")
var bad=first;bad.validation="VERIFIED";reject(bad);bad=first;bad.id="../../outside";reject(bad);bad=first;bad.controls.worker=99;reject(bad)
bad=first;bad.controls.customPercent=1;reject(bad);bad=first;bad.controls.spatialPercent=1;reject(bad);bad=first;bad.controls.fps=120;reject(bad)
bad=first;bad.controls.archiveVerification=true;reject(bad);bad=first;bad.controls.clockFeedback=true;bad.controls.clockTimed=true;reject(bad)
for i in 1..<16{var p=first;p.id=UUID().uuidString;p.name="Experiment\(i)";_=try store.save(p,device:"iPad16,5")}
assert(store.load(device:"iPad16,5").count==16)
var extra=first;extra.id=UUID().uuidString;do{_=try store.save(extra,device:"iPad16,5");fatalError("exceeded capacity")}catch{}
try store.remove(first,device:"iPad16,5");assert(store.load(device:"iPad16,5").count==15)
let huge=root.appendingPathComponent("oversized.json");try Data(repeating:32,count:65537).write(to:huge)
do{_=try store.decode(url:huge,device:"iPad16,5");fatalError("accepted oversized data")}catch{}
let reports=EfficiencyDelayedReportStore(directory:root.appendingPathComponent("reports"),maximumBytes:1024,maximumReports:8)
for _ in 0..<12{_=try reports.save(Data("{\"host_metric\":1}".utf8))}
let keep=reports.directory.appendingPathComponent("keep.txt");try Data("keep".utf8).write(to:keep)
_=try reports.save(Data("{}".utf8));assert(reports.listed().count==8&&FileManager.default.fileExists(atPath:keep.path))
do{_=try reports.save(Data(repeating:32,count:1025));fatalError("accepted oversized report")}catch{}
do{_=try reports.save(Data("not json".utf8));fatalError("accepted invalid JSON")}catch{}
bad=first;bad.controls.execution=HuskExecutionOptions(prefill:3,commandBufferLimit:8,initializationParking:true);reject(bad)
assert(!EfficiencyHardware.identifier().isEmpty)
print("Actual device/game/profile constraints, bounded reads/capacity and owned OS-report rotation passed")
''')
   exe=p/'check';subprocess.run(['swiftc',str(ROOT/'src/app/Husk/HuskExecutionOptions.swift'),str(ROOT/'src/app/Husk/EfficiencyProfileStore.swift'),str(p/'main.swift'),'-o',str(exe)],check=True);subprocess.run([str(exe),str(p/'data')],check=True)
if __name__=='__main__':unittest.main()
