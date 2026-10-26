// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

enum EfficiencyHardware {
    static func identifier() -> String {
        var value = utsname(); uname(&value)
        let capacity = MemoryLayout.size(ofValue: value.machine)
        return withUnsafePointer(to: &value.machine) { $0.withMemoryRebound(to: CChar.self, capacity: capacity) { String(cString: $0) } }
    }
}

struct EfficiencyProfile: Codable, Identifiable, Equatable {
    struct Controls: Codable, Equatable {
        var graphics: String, orientation: String, window: String
        var resolution: Int, customPercent: Int, fps: Int, worker: Int, submission: Int
        var spatial: Bool, spatialPercent: Int, archive: Int
        var archiveVerification: Bool, engineOnly: Bool, clockTimed: Bool, clockFeedback: Bool
    }
    var version = 1
    var id: String = UUID().uuidString
    var name: String, device: String, game: String, build: String
    var created: Date = Date()
    var validation = "UNVERIFIED_LOCAL_EXPERIMENT"
    var controls: Controls
    func validated(for currentDevice: String, game currentGame: String? = nil) throws -> EfficiencyProfile {
        let c = controls
        guard version == 1, UUID(uuidString: id) != nil,
              !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, name.count <= 64,
              name.rangeOfCharacter(from: .controlCharacters) == nil,
              device == currentDevice, !device.isEmpty, device.count <= 64,
              !game.isEmpty, game.count <= 256, (currentGame == nil || game == currentGame),
              build.count <= 128, validation == "UNVERIFIED_LOCAL_EXPERIMENT",
              ["automatic", "gameDefault", "sharpHigh", "efficientHigh"].contains(c.graphics),
              ["auto", "landscape", "portrait"].contains(c.orientation),
              ["auto", "window", "fullScreen"].contains(c.window),
              [-1,0,65,70,75,80,85,90,95,100].contains(c.resolution), (65...100).contains(c.customPercent),
              [30,60].contains(c.fps), (0...4).contains(c.worker), (0...1).contains(c.submission),
              [80,85,90,95].contains(c.spatialPercent), (0...2).contains(c.archive),
              (!c.archiveVerification || c.archive == 2),
              !(c.clockTimed && c.clockFeedback) else { throw Failure.invalid }
        return self
    }
    enum Failure: Error { case invalid, tooLarge, capacity }
}

struct EfficiencyProfileStore {
    let directory: URL
    static let maximumBytes = 65_536, maximumProfiles = 16
    private func owned() -> [URL] {
        ((try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? []).filter { $0.lastPathComponent.hasPrefix("profile-") && $0.pathExtension == "json" }
    }
    func load(device: String, game: String? = nil) -> [EfficiencyProfile] {
        let urls = ((try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.lastPathComponent.hasPrefix("profile-") && $0.pathExtension == "json" }.sorted { $0.lastPathComponent < $1.lastPathComponent }
        return urls.prefix(Self.maximumProfiles).compactMap { url in
            guard let p = try? decode(url: url, device: device),
                  url.lastPathComponent == filename(p.id) else { return nil }
            return game == nil || p.game == game ? p : nil
        }.sorted { $0.created > $1.created }
    }
    private func filename(_ id: String) -> String { "profile-\(UUID(uuidString: id)?.uuidString ?? "invalid").json" }
    func decode(url: URL, device: String) throws -> EfficiencyProfile {
        let handle = try FileHandle(forReadingFrom: url); defer { try? handle.close() }
        let data = try handle.read(upToCount: Self.maximumBytes + 1) ?? Data()
        guard data.count <= Self.maximumBytes else { throw EfficiencyProfile.Failure.tooLarge }
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(EfficiencyProfile.self, from: data).validated(for: device)
    }
    @discardableResult func save(_ profile: EfficiencyProfile, device: String) throws -> URL {
        let p = try profile.validated(for: device)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let url = directory.appendingPathComponent(filename(p.id))
        guard FileManager.default.fileExists(atPath: url.path) || owned().count < Self.maximumProfiles else { throw EfficiencyProfile.Failure.capacity }
        let encoder = JSONEncoder(); encoder.dateEncodingStrategy = .iso8601; encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let data = try encoder.encode(p)
        guard data.count <= Self.maximumBytes else { throw EfficiencyProfile.Failure.tooLarge }
        try data.write(to: url, options: .atomic); return url
    }
    func remove(_ profile: EfficiencyProfile, device: String) throws {
        let p = try profile.validated(for: device)
        try FileManager.default.removeItem(at: directory.appendingPathComponent(filename(p.id)))
    }
}

/// Explicitly owned delayed-report files only. Caller serialises access on its
/// utility queue; this policy is independent of MetricKit delivery/attribution.
struct EfficiencyDelayedReportStore {
    let directory: URL
    let maximumBytes: Int
    let maximumReports: Int
    func listed() -> [URL] {
        let urls = (try? FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: [.contentModificationDateKey])) ?? []
        return urls.filter { $0.lastPathComponent.hasPrefix("metrickit-") && $0.pathExtension == "json" }.sorted {
            let a = (try? $0.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            let b = (try? $1.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
            return a == b ? $0.lastPathComponent < $1.lastPathComponent : a > b
        }
    }
    @discardableResult func save(_ data: Data) throws -> URL {
        guard maximumReports > 0, maximumBytes > 0, data.count <= maximumBytes else { throw EfficiencyProfile.Failure.tooLarge }
        _ = try JSONSerialization.jsonObject(with: data)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let file = directory.appendingPathComponent("metrickit-\(UUID().uuidString).json")
        try data.write(to: file, options: .atomic)
        for old in listed().dropFirst(maximumReports) { try? FileManager.default.removeItem(at: old) }
        return file
    }
}
