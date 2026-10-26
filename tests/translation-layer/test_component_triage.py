#!/usr/bin/env python3
"""Actual Swift evidence triage; observations never become energy/root-cause gates."""
import subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
class TriageTests(unittest.TestCase):
 @unittest.skipUnless(sys.platform=='darwin','Apple Swift/Foundation check runs in IPA CI')
 def test_actual_triage_coverage_scopes_no_false_cause_or_energy(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'main.swift').write_text(r'''
import Foundation
func findings(_ x:[String:Any])->[[String:Any]]{x["findings"] as! [[String:Any]]}
func has(_ x:[String:Any],_ name:String)->Bool{findings(x).contains{$0["component"] as? String == name}}
let empty=EfficiencyComponentTriage.build([:]);assert(findings(empty).isEmpty)
assert(empty["root_cause_confirmed"] as? Bool == false && (empty["automatically_passed_roadmap_gates"] as! [String]).isEmpty)
assert(empty["energy_improvement"] as? String == "UNVERIFIED")
let input:[String:Any] = ["summary":["slow_pipeline_calls":2,"worst_pipeline_ns":125_000_000,"dropped_frame_intervals_cumulative":1],
 "windows":[["interval_count":120,"p95_ms":20.9,"worst_ms":300,"slow_pipeline_calls":0]],
 "component_sampling":["requested":true,"components":[["component":"futex_wait_operation","completed_sampled_calls":8,"sampled_wall_ns":8_000_000,"sampled_caller_cpu_ns":80_000]]],
 "driver_phases":["available":true,"query_serial":2,"phases":[["component":"metal_library","new_calls_since_previous_query":1,"new_total_ms_estimated":100,"latest_event_ms":100,"lifetime_max_ms":5000], ["component":"old_encoding_max","new_calls_since_previous_query":0,"new_total_ms_estimated":0,"latest_event_ms":0,"lifetime_max_ms":9000]]],
 "native_pipeline_archive":["verification_requested":true,"verification_attempts":3,"verification_failed_calls":1,"metal_archive_requirement_satisfied_calls":2,"last_verification_error_domain":"test","last_verification_error_code":9]]
let before=try JSONSerialization.data(withJSONObject:input,options:[.sortedKeys])
let t=EfficiencyComponentTriage.build(input)
for name in ["pipeline_creation","non_pipeline_pacing","measurement_coverage","futex_wait_operation","metal_library","native_archive_requirement"]{assert(has(t,name))}
assert(!has(t,"old_encoding_max"))
let pace=findings(t).first{$0["component"] as? String == "non_pipeline_pacing"}!
assert(pace["confidence"] as? String == "HYPOTHESIS")
assert((pace["observation"] as! String).contains("in-flight"))
let text=EfficiencyComponentTriage.text(t);assert(text.contains("[M2/M5 pipeline_creation]"))
assert(text.contains("Failed attempts are not necessarily archive misses"))
let after=try JSONSerialization.data(withJSONObject:input,options:[.sortedKeys]);assert(after == before)
assert(JSONSerialization.isValidJSONObject(t))
let invalid=EfficiencyComponentTriage.build(["summary":["slow_pipeline_calls":true,"worst_pipeline_ns":Double.nan],"windows":[["interval_count":120,"p95_ms":Double.infinity,"slow_pipeline_calls":0]]])
assert(!has(invalid,"pipeline_creation") && !has(invalid,"non_pipeline_pacing"))
let nested=EfficiencyComponentTriage.build(["component_sampling":["requested":true,"components":[["component":"once_slow_path_including_initializer","completed_sampled_calls":4,"sampled_wall_ns":40,"sampled_caller_cpu_ns":30]]]])
assert(has(nested,"once_slow_path_including_initializer"))
assert(JSONSerialization.isValidJSONObject(nested))
print("Actual component triage: scoped evidence, exclusions/coverage, driver lifetime limits, no false cause/energy passed")
''')
   exe=p/'check';subprocess.run(['swiftc',str(ROOT/'src/app/Husk/EfficiencyComponentTriage.swift'),str(p/'main.swift'),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
if __name__=='__main__':unittest.main()
