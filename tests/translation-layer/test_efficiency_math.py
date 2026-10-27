#!/usr/bin/env python3
"""Compile the actual Foundation-only Swift calculation/export code on macOS CI."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]

@unittest.skipUnless(shutil.which('swiftc'), 'Swift compiler unavailable; macOS IPA CI runs these checks')
class EfficiencyMathTests(unittest.TestCase):
    def test_cpu_battery_and_json_nulls(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'main.swift'
            p.write_text('''import Foundation
func check(_ value: Bool) { precondition(value) }
check(EfficiencyMath.cpuPercent(previous: 2, current: 5, elapsed: 2, included: true) == 150)
check(EfficiencyMath.cpuPercent(previous: -1, current: 5, elapsed: 2, included: true) == nil)
check(EfficiencyMath.cpuPercent(previous: 5, current: 4, elapsed: 2, included: true) == nil)
check(EfficiencyMath.cpuPercent(previous: 2, current: 5, elapsed: 0, included: true) == nil)
check(EfficiencyMath.cpuPercent(previous: 2, current: 5, elapsed: 2, included: false) == nil)
var battery = EfficiencyMath.Battery()
check(battery.rate == nil)
battery.sample(time: 0, level: -1, unplugged: true, included: true)
check(battery.rate == nil)
battery.sample(time: 0, level: 1, unplugged: true, included: true)
battery.sample(time: 1800, level: 0.95, unplugged: true, included: true)
battery.sample(time: 3600, level: 0.9, unplugged: true, included: true)
check(abs(battery.rate! - 10) < 0.0001)
battery.sample(time: 4000, level: 0.8, unplugged: false, included: true)
battery.sample(time: 5000, level: 0.7, unplugged: true, included: false)
check(battery.seconds == 3600)
battery.sample(time: 6000, level: 0.7, unplugged: true, included: true)
battery.sample(time: 6200, level: 0.8, unplugged: true, included: true)
check(battery.seconds == 3600) // increase resets anchor, not negative drain
check(battery.rate == nil)
check(battery.status.contains("INCONCLUSIVE"))
battery.resetAnchor()
battery.sample(time: 7200, level: 0.6, unplugged: true, included: true)
check(battery.seconds == 3600)
var flat = EfficiencyMath.Battery()
flat.sample(time: 0, level: 0.7, unplugged: true, included: true)
flat.sample(time: 300, level: 0.7, unplugged: true, included: true)
check(flat.rate == nil); check(flat.seconds == 300); check(flat.sampleCount == 2)
check(flat.status.contains("UNRESOLVED"))
var short = EfficiencyMath.Battery()
short.sample(time: 0, level: 0.4, unplugged: true, included: true)
short.sample(time: 226, level: 0.35, unplugged: true, included: true)
check(short.rate == nil && short.arithmeticRate != nil && short.status.contains("INSUFFICIENT"))
let event = EfficiencyMath.eventFields(type: "runtime", detail: "ue4 pipeline stall: result 0, finished monotonic 105.25 s", recorded: 110, origin: 100)
check((event["plan_ids"] as? [String]) == ["M2", "PIPE-01"])
check((event["occurred_t"] as? Double) == 5.25)
check((event["recorded_t"] as? Double) == 10)
check((event["outcome"] as? String) == "api_success")
check((event["benefit_validation"] as? String) == "unverified")
let clockEvent = EfficiencyMath.eventFields(type: "runtime", detail: "[M4/M6 present-clock] unsupported timing chain; result -7", recorded: 110, origin: 100)
check((clockEvent["plan_ids"] as? [String]) == ["M4", "M6", "M3"])
check((clockEvent["outcome"] as? String) == "api_failure")
func gpu(_ a: Double, _ b: Double, _ lo: Double, _ hi: Double) -> [String: Any] {
    ["gpu_start_media_seconds": a, "gpu_end_media_seconds": b, "sample_start_media_seconds": lo, "sample_end_media_seconds": hi]
}
check(EfficiencyMath.intervalUnion([(100,101),(100.5,102),(110,110.5)]) == 2.5)
check(EfficiencyMath.gpuIntervalUnion([]) == 0)
check(abs(EfficiencyMath.gpuIntervalUnion([gpu(99, 100.5, 100, 101), gpu(100.3, 102, 100, 101), gpu(110.2, 110.4, 110, 111)]) - 1.2) < 0.00001)
check(EfficiencyMath.gpuIntervalUnion([gpu(0, .nan, 0, 1), gpu(2, 3, 0, 1)]) == 0)
let lifecycle = EfficiencyMath.eventFields(type: "runtime", detail: "[M1/M6/M9 lifecycle] apply begin", recorded: 101, origin: 100)
check(lifecycle["subsystem"] as? String == "native_lifecycle")
check(lifecycle["plan_ids"] as? [String] == ["M1", "M6", "M9"])
let data = try EfficiencyMath.json(["schema_version": 1, "unavailable": NSNull(), "events": [["detail": "quote \\\" / newline\\n"]]])
let decoded = try JSONSerialization.jsonObject(with: data) as! [String: Any]
check(decoded["unavailable"] is NSNull)
check((decoded["schema_version"] as? Int) == 1)
''')
            binary=Path(d)/'check'
            subprocess.run(['swiftc',str(ROOT/'src/app/Husk/EfficiencyMath.swift'),str(p),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)
if __name__=='__main__':unittest.main()
