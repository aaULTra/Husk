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
        private(set) var sampleCount = 0, increases = 0
        private(set) var firstLevel: Double?, lastLevel: Double?
        var status: String {
            if seconds <= 0 { return "UNAVAILABLE: no valid included unplugged interval" }
            if increases > 0 { return "INCONCLUSIVE: reported level increased in unplugged samples" }
            if drain == 0 { return "UNRESOLVED: no reported battery decrease; not zero energy" }
            return "ESTIMATED: coarse percentage-point drain; not measured power"
        }
        mutating func resetAnchor() { anchor = nil }
        mutating func sample(time: Double, level: Double, unplugged: Bool, included: Bool) {
            guard included, unplugged, time.isFinite, level.isFinite, (0...1).contains(level) else { anchor = nil; return }
            sampleCount += 1
            if firstLevel == nil { firstLevel = level }; lastLevel = level
            if let (_, before) = anchor, level > before { increases += 1 }
            if let (at, before) = anchor, time > at, level <= before {
                drain += (before - level) * 100; seconds += time - at
            }
            anchor = (time, level)
        }
        var rate: Double? { seconds > 0 && drain > 0 && increases == 0 ? drain * 3600 / seconds : nil }
    }
    static func eventFields(type: String, detail: String, recorded: Double, origin: Double) -> [String: Any] {
        var ids = ["M1", "MEAS-01"], subsystem = "monitor", outcome = "observed"
        if detail.hasPrefix("ue4 pipeline") { ids = ["M2", "PIPE-01"]; subsystem = "pipeline" }
        else if detail.hasPrefix("ue4 cache") { ids = ["M2", "CACHE-01"]; subsystem = "cache" }
        else if detail.hasPrefix("thread-policy") { ids = ["M7", "WORK-01", "WORK-02"]; subsystem = "worker_policy" }
        else if detail.hasPrefix("ue4 timing") { ids = ["M4", "BUG-02"]; subsystem = "frame_pacing" }
        else if detail.hasPrefix("ue4 submission") { ids = ["M6", "SUBMIT-01"]; subsystem = "submission" }
        else if detail.hasPrefix("vulkan: vkCreateSwapchain") { ids = ["M6", "BASE-01"]; subsystem = "presentation" }
        // API outcome is distinct from measured performance/energy validation.
        if let range = detail.range(of: "result "), let token = detail[range.upperBound...].split(whereSeparator: { $0 == "," || $0.isWhitespace }).first,
           let code = Int(token) { outcome = code < 0 ? "api_failure" : code == 0 ? "api_success" : "api_status" }
        var row: [String: Any] = ["t": recorded - origin, "recorded_t": recorded - origin,
            "occurred_t": NSNull(), "type": type, "detail": detail, "plan_ids": ids,
            "subsystem": subsystem, "outcome": outcome, "benefit_validation": "unverified"]
        if let range = detail.range(of: "finished monotonic "),
           let token = detail[range.upperBound...].split(whereSeparator: { $0.isWhitespace }).first,
           let time = Double(token), time.isFinite { row["occurred_t"] = time - origin }
        return row
    }
    static func json(_ report: [String: Any]) throws -> Data {
        try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
    }
}
