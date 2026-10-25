// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation

/// Portable calculation/export policy, shared by the UI and executable tests.
enum EfficiencyMath {
    static func cpuPercent(previous: Double, current: Double, elapsed: Double, included: Bool) -> Double? {
        guard included, previous.isFinite, current.isFinite, elapsed.isFinite,
              previous >= 0, current >= previous, elapsed > 0 else { return nil }
        return (current - previous) / elapsed * 100 // 100% = one logical CPU
    }
    struct Battery {
        private var anchor: (Double, Double)?
        private(set) var drain = 0.0, seconds = 0.0
        mutating func resetAnchor() { anchor = nil }
        mutating func sample(time: Double, level: Double, unplugged: Bool, included: Bool) {
            guard included, unplugged, time.isFinite, level.isFinite, (0...1).contains(level) else { anchor = nil; return }
            if let (at, before) = anchor, time > at, level <= before {
                drain += (before - level) * 100; seconds += time - at
            }
            anchor = (time, level)
        }
        var rate: Double? { seconds > 0 ? drain * 3600 / seconds : nil }
    }
    static func json(_ report: [String: Any]) throws -> Data {
        try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
    }
}
