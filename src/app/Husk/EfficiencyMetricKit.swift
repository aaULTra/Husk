// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation
import MetricKit
import SwiftUI

/// Periodic OS payloads concern the hosting process. They cannot isolate a
/// translated guest game, supply instant power, or validate a current session.
final class EfficiencyMetricKit: NSObject, ObservableObject, MXMetricManagerSubscriber {
    static let shared = EfficiencyMetricKit()
    static var enabledByPreference: Bool { UserDefaults.standard.bool(forKey: preference) }
    private static let preference = "husk.efficiency.delayed-metrickit"
    private let queue = DispatchQueue(label: "husk.metrickit.archive", qos: .utility)
    @Published private(set) var enabled = false
    @Published private(set) var files: [URL] = []
    @Published private(set) var message = "No delayed OS reports received. Availability and LiveContainer attribution need validation."
    private var subscribed = false
    private let maximumBytes = 4 * 1024 * 1024, maximumReports = 8
    override private init() {
        super.init()
        setEnabled(UserDefaults.standard.bool(forKey: Self.preference))
        if enabled { reload() }
    }
    func setEnabled(_ value: Bool) {
        UserDefaults.standard.set(value, forKey: Self.preference); enabled = value
        if value && !subscribed { MXMetricManager.shared.add(self); subscribed = true }
        if !value && subscribed { MXMetricManager.shared.remove(self); subscribed = false }
    }
    func didReceive(_ payloads: [MXMetricPayload]) {
        for payload in payloads.suffix(maximumReports) { store(payload.jsonRepresentation(), kind: "periodic_metrics") }
    }
    func didReceive(_ payloads: [MXDiagnosticPayload]) {
        for payload in payloads.suffix(maximumReports) { store(payload.jsonRepresentation(), kind: "os_diagnostic") }
    }
    private var directory: URL { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("DelayedOSReports") }
    private var storage: EfficiencyDelayedReportStore { .init(directory: directory, maximumBytes: maximumBytes, maximumReports: maximumReports) }
    private func listed() -> [URL] { storage.listed() }
    private func store(_ data: Data, kind: String) {
        guard UserDefaults.standard.bool(forKey: Self.preference) else { return }
        queue.async {
            guard UserDefaults.standard.bool(forKey: Self.preference) else { return }
            do {
                guard data.count <= self.maximumBytes else { throw EfficiencyProfile.Failure.tooLarge }
                let payload = try JSONSerialization.jsonObject(with: data)
                let record: [String: Any] = ["schema_version": 1, "type": kind, "plan_ids": ["M3", "M1"],
                    "received_utc": ISO8601DateFormatter().string(from: Date()), "device_identifier": EfficiencyHardware.identifier(),
                    "reported_bundle_identifier": Bundle.main.bundleIdentifier ?? "UNAVAILABLE",
                    "build_sha": Bundle.main.object(forInfoDictionaryKey: "HuskBuildCommit") as? String ?? "UNAVAILABLE",
                    "attribution": "Delayed OS payload for the hosting process/bundle; LiveContainer can affect bundle mapping. Not isolated Dungeons or instant/session energy. No inferred watts or numerical temperature.", "os_payload": payload]
                let encoded = try JSONSerialization.data(withJSONObject: record, options: [.prettyPrinted, .sortedKeys])
                guard encoded.count <= self.maximumBytes else { throw EfficiencyProfile.Failure.tooLarge }
                _ = try self.storage.save(encoded)
                let files = Array(self.listed().prefix(self.maximumReports))
                DispatchQueue.main.async { self.files = files; self.message = "Delayed OS report saved. Host attribution only; not a current-game energy result." }
            } catch { DispatchQueue.main.async { self.message = "[M3 MetricKit] Report could not be archived: \(error.localizedDescription)" } }
        }
    }
    func reload() {
        queue.async { let files = Array(self.listed().prefix(self.maximumReports)); DispatchQueue.main.async { self.files = files } }
    }
    var summary: [String: Any] {
        ["plan_ids": ["M3", "M1"], "requested": enabled, "retained_reports": files.count,
         "report_files": files.map(\.lastPathComponent), "maximum_reports": maximumReports,
         "maximum_bytes_per_report": maximumBytes, "status": message,
         "scope": "Opt-in delayed MetricKit host-process reports. Raw payloads shared separately; no instant game power/GPU/thermal attribution."]
    }
}
