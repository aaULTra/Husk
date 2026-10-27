#!/usr/bin/env python3
"""Run the actual Swift inspection policy; Apple CI also compiles its SwiftUI wiring."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('swiftc'), 'Swift compiler unavailable; required Apple IPA CI executes this policy')
class ArchiveStatusTests(unittest.TestCase):
    def test_actual_policy_preserves_unknowns_acknowledges_repeated_taps_and_explains_every_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / 'main.swift'
            main.write_text('''import Foundation
func status(_ mode: Int = 2, _ configuration: Int = 1, _ api: Bool = true,
            _ snapshot: Bool = true, _ supported: Bool = true, _ pending: UInt32 = 0,
            _ preparing: Bool = false) -> NativeArchivePresentation.Status {
    NativeArchivePresentation.status(mode: mode, configuration: configuration,
        apiAvailable: api, snapshotValid: snapshot, supported: supported, pending: pending, preparing: preparing)
}
precondition(status(0).code == "off")
precondition(status(0).message.contains("when this game launched"))
precondition(status(1).code == "driver_only")
let states = [0: "not_configured", 2: "wrong_project", 3: "graphics_disabled",
              4: "driver_api_missing", 5: "configuration_rejected", 6: "device_ended", 999: "unknown_configuration"]
for (configuration, code) in states { precondition(status(2, configuration).code == code) }
precondition(status(2, 1, false).code == "driver_api_missing")
precondition(status(2, 1, true, false).code == "snapshot_unavailable")
precondition(status(2, 1, true, true, false).code == "support_unconfirmed")
precondition(status().code == "empty")
precondition(status().message.contains("not proof"))
let ready = status(2, 1, true, true, true, 3)
precondition(ready.code == "ready" && ready.message.contains("3 captured"))
precondition(status(2, 1, true, true, true, 3, true).code == "preparing")
let first = NativeArchivePresentation.acknowledgement(sequence: 1, utc: "same-second", status: ready, pending: 3, restored: 17)
let second = NativeArchivePresentation.acknowledgement(sequence: 2, utc: "same-second", status: ready, pending: 3, restored: 17)
precondition(first != second && first.contains("Inspection #1") && second.contains("Inspection #2"))
precondition(second.contains("Pending: 3") && second.contains("not cache-hit"))
let unavailable = NativeArchivePresentation.acknowledgement(sequence: 3, utc: "later", status: status(0), pending: nil, restored: nil)
precondition(unavailable.contains("UNAVAILABLE") && !unavailable.contains("Pending: 0"))
func blocker(_ running: Bool = false, _ exporting: Bool = false, _ preparing: Bool = false,
             _ visible: Bool = true, _ active: Bool = true) -> String? {
    NativeArchivePresentation.preparationBlocker(running: running, exporting: exporting,
        preparing: preparing, gameVisible: visible, active: active)
}
precondition(blocker() == nil)
precondition(blocker(true)?.contains("Stop") == true)
precondition(blocker(false, true)?.contains("export") == true)
precondition(blocker(false, false, true)?.contains("already") == true)
precondition(blocker(false, false, false, false)?.contains("attached") == true)
precondition(blocker(false, false, false, true, false)?.contains("foreground") == true)
''')
            binary = root / 'check'
            subprocess.run(['swiftc', str(ROOT / 'src/app/Husk/NativeArchivePresentation.swift'), str(main), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
