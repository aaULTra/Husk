// SPDX-License-Identifier: GPL-2.0-or-later
import SwiftUI
import UIKit

/// "That game closed Husk": noticed at the next launch, explained, and easy to send on.
///
/// A game that crashes takes Husk with it -- it runs in Husk's own process -- so nothing can be shown at the moment it
/// happens. Instead, a note is written when a game starts and removed when it is closed the normal way. A note still there
/// at the next launch means the game did not get to close: Husk shows what it knows from the previous run's log (kept as
/// husk-prev.log) and offers the whole report to share.
@MainActor
final class CrashReport: ObservableObject {
    static let shared = CrashReport()

    struct Report: Identifiable {
        let id = UUID()
        let game: String
        let appID: String
        let cause: Cause
        let when: Date?
        /// The previous run's last lines, for the sheet.
        let excerpt: [String]
        let context: [String: Any]
    }

    enum Cause {
        case signal(Int)        // a fatal signal the crash handler recorded
        case startFailed        // the runtime said the game could not be started, and Husk closed after that
        case unknown            // no record of why: memory (iOS ends the app without a word), or Husk swiped away
        case diagnosed(AppDiagnosis)    // the run's log says why (AppDiagnosis)

        var title: String {
            switch self {
            case .signal: return "The game crashed"
            case .startFailed: return "The game could not start"
            case .unknown: return "Husk closed while the game was running"
            case .diagnosed(let d): return d.title
            }
        }
        var detail: String {
            switch self {
            case .signal(let s):
                let name = [11: "SIGSEGV, a bad memory access", 6: "SIGABRT, the game or a library gave up",
                            4: "SIGILL, an instruction this device does not run", 8: "SIGFPE, an arithmetic error",
                            12: "SIGSYS, a system call iOS does not allow"][s] ?? "signal \(s)"
                return "It stopped with \(name). The report has the full log of that run."
            case .startFailed:
                return "The runtime could not start it. The report says which part was missing."
            case .unknown:
                return "No fatal cause was recorded. A hang/watchdog, an operating-system termination, a host failure or closing the app can leave this record. The log alone does not distinguish them; an iPadOS/LiveContainer incident report may identify the cause."
            case .diagnosed(let d):
                return d.detail
            }
        }
    }

    @Published var pending: Report?

    private static var docs: URL { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0] }
    private static var marker: URL { docs.appendingPathComponent("running-game.json") }
    /// Survives a hard process death and can be opened before Husk is restarted.
    private static var activeRecord: URL { HuskLog.reportsDirectory.appendingPathComponent("ACTIVE-GAME.txt") }
    static var previousLogURL: URL { docs.appendingPathComponent("husk-prev.log") }

    // MARK: the note

    private static var running: TLApp?
    private static var session: RunningGameSession?
    private static var observers: [NSObjectProtocol] = []

    /// A game is starting: if Husk ends before `gameEnded`, the next launch will say so.
    ///
    /// Keep interruption context rather than deleting evidence during inactive
    /// transitions. An uncleared marker reports an unclean end, not a proven
    /// crash, memory kill or watchdog. Normal game closure still removes it.
    static func gameStarted(_ app: TLApp) {
        if running?.id != app.id || session == nil {
            session = RunningGameSession(id: app.id, label: app.label,
                build: Bundle.main.object(forInfoDictionaryKey: "HuskBuildCommit") as? String ?? "UNAVAILABLE",
                time: Date().timeIntervalSince1970)
        }
        running = app
        writeMarker()
        if observers.isEmpty {
            let nc = NotificationCenter.default
            observers.append(nc.addObserver(forName: UIApplication.willResignActiveNotification, object: nil, queue: .main) { _ in
                noteLifecycle("application_inactive")
            })
            observers.append(nc.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil, queue: .main) { _ in
                noteLifecycle("application_active")
            })
            observers.append(nc.addObserver(forName: UIApplication.didEnterBackgroundNotification, object: nil, queue: .main) { _ in
                noteLifecycle("application_background")
            })
        }
    }

    private static func writeMarker() {
        guard running != nil, let session else { return }
        if let data = try? JSONEncoder().encode(session) { try? data.write(to: marker, options: .atomic) }
        // A human-readable breadcrumb in Files, even if UIKit and Swift never
        // have another chance to run. Written before entering the game runtime.
        let last = session.lastState
        let text = """
        Husk game session (uncleared does not prove a crash)
        =================================================
        Game: \(session.label)
        Session: \(session.session)
        Build: \(session.build)
        Device: \(HuskLog.deviceModel), iOS \(UIDevice.current.systemVersion)
        Last recorded state: \(last)
        Started (Unix time): \(session.time)
        Relevant live files: Documents/husk.log, Documents/husk-native.log
        Fatal-signal record: Documents/Crash Reports/fatal-signal-current.txt
        For LiveContainer guests, use the guest's Documents folder in the host.
        If Husk disappears, these files can be copied in Files without reopening it.
        No native crash signature means the OS may have killed the process.
        """
        try? FileManager.default.createDirectory(at: HuskLog.reportsDirectory, withIntermediateDirectories: true)
        try? text.write(to: activeRecord, atomically: true, encoding: .utf8)
    }
    static func noteLifecycle(_ name: String) {
        guard running != nil else { return }
        session?.note(name, time: Date().timeIntervalSince1970)
        writeMarker()
    }

    /// The game was closed the normal way.
    static func gameEnded() {
        running = nil
        session = nil
        try? FileManager.default.removeItem(at: marker)
        try? FileManager.default.removeItem(at: activeRecord)
    }

    /// At launch: was a game running when Husk last ended?
    func checkPreviousRun() {
        guard pending == nil,
              let data = try? Data(contentsOf: Self.marker),
              let info = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
        let mainLog = Self.readTail(Self.previousLogURL, bytes: 1024 * 1024)
        let nativeLog = Self.readTail(HuskLog.previousNativeLogURL, bytes: 1024 * 1024)
        let fatalLog = Self.readTail(HuskLog.previousSignalLogURL, bytes: 8192)
        let lines = RuntimeLogEvidence.currentLines(mainLog + "\n" + nativeLog + "\n" + fatalLog)
        var cause = Cause.unknown
        if let n = RuntimeLogEvidence.fatalSignal(lines) {
            cause = .signal(n)
        } else if lines.contains(where: { $0.contains("the game could not be started") || $0.contains("native: launch refused") }) {
            cause = .startFailed
        }
        // A warning/heuristic must never override a recorded fatal signal.
        if case .unknown = cause, let d = AppDiagnosis.fromLog(lines.joined(separator: "\n")) { cause = .diagnosed(d) }
        let time = (info["time"] as? Double).map { Date(timeIntervalSince1970: $0) }
        pending = Report(game: info["label"] as? String ?? "A game", appID: info["id"] as? String ?? "",
                         cause: cause, when: time, excerpt: Array(Self.interesting(lines).suffix(14)), context: info)
        HuskLog.log("crash", "\(pending!.game) did not close normally last run: \(cause.title)")
        // Do this automatically rather than only when the user opens the sheet.
        // Keep the original marker if saving fails, so evidence can be retried.
        if let saved = Self.writeReport(pending!) {
            HuskLog.log("crash", "recovered Files report: \(saved.path)")
            try? FileManager.default.removeItem(at: Self.marker)
            try? FileManager.default.removeItem(at: Self.activeRecord)
        } else {
            HuskLog.log("crash", "WARNING: could not archive previous game logs; original marker retained")
        }
        switch cause {
        case .signal: GameStatusStore.shared.record(pending!.appID, .crashed)
        case .startFailed: GameStatusStore.shared.record(pending!.appID, .failed)
        case .unknown: break
        case .diagnosed(let d): GameStatusStore.shared.record(pending!.appID, .crashed, diagnosis: d)
        }
    }

    /// The lines of a log worth a glance: the runtime's and the crash handler's, not the JIT's housekeeping.
    private static func interesting(_ lines: [String]) -> [String] {
        lines.filter { l in
            !l.contains("csops status") && !l.contains("[husk-jit]") && !l.contains("[jit]") && !l.contains("[guest]")
                && !l.contains("[boot]") && !l.contains("[prev]")
        }
    }

    // MARK: the report

    /// Read only a bounded tail: huge or malformed native logs must not exhaust
    /// iOS memory while Husk is trying to recover from a previous crash.
    private static func readTail(_ url: URL, bytes: Int) -> String {
        guard let handle = try? FileHandle(forReadingFrom: url) else { return "(not captured)\n" }
        defer { try? handle.close() }
        let size = handle.seekToEndOfFile()
        if size > UInt64(bytes) { handle.seek(toFileOffset: size - UInt64(bytes)) }
        let data = handle.readData(ofLength: bytes)
        return String(decoding: data, as: UTF8.self)
    }

    private static func reportDirectory(_ report: Report) -> URL {
        let session = (report.context["session"] as? String ?? "unknown")
            .filter { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "-") }
        let epoch = Int(report.when?.timeIntervalSince1970 ?? 0)
        return HuskLog.reportsDirectory.appendingPathComponent("crash-\(epoch)-\(String(session.prefix(40)))", isDirectory: true)
    }

    /// Save complete logs (up to a bounded tail) beside a one-file report. A cap
    /// prevents runaway native logging from consuming the entire device.
    private static func preserve(_ source: URL, as destination: URL) {
        let fm = FileManager.default
        guard !fm.fileExists(atPath: destination.path),
              fm.fileExists(atPath: source.path) else { return }
        let maxBytes = 16 * 1024 * 1024
        let size = (try? fm.attributesOfItem(atPath: source.path)[.size] as? NSNumber)?.int64Value ?? 0
        if size <= Int64(maxBytes) {
            try? fm.copyItem(at: source, to: destination)
        } else {
            let header = "[Only the last 16 MiB of this oversized log was preserved; original \(size) bytes.]\n"
            let contents = header + readTail(source, bytes: maxBytes)
            try? contents.write(to: destination, atomically: true, encoding: .utf8)
        }
    }

    /// Keep the latest eight game-failure directories. Do not prune files while
    /// a report is being written or remove the active-game breadcrumb.
    private static func pruneArchives(keeping current: URL) {
        let fm = FileManager.default
        guard let urls = try? fm.contentsOfDirectory(at: HuskLog.reportsDirectory,
                                                       includingPropertiesForKeys: [.isDirectoryKey]) else { return }
        let old = urls.filter { $0.lastPathComponent.hasPrefix("crash-") && $0 != current }
            .sorted { $0.lastPathComponent > $1.lastPathComponent }
        for url in old.dropFirst(7) { try? fm.removeItem(at: url) }
    }

    /// In Files > On My iPhone/iPad > Husk > Crash Reports > crash-... .
    /// A report is saved automatically on the next launch, even without the UI.
    static func writeReport(_ r: Report) -> URL? {
        let info = Bundle.main.infoDictionary ?? [:]
        let folder = reportDirectory(r)
        do { try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true) }
        catch { return nil }
        let contextData = try? JSONSerialization.data(withJSONObject: r.context, options: [.prettyPrinted, .sortedKeys])
        let contextText = contextData.flatMap { String(data: $0, encoding: .utf8) } ?? "(no recorded context)"
        if let contextData {
            try? contextData.write(to: folder.appendingPathComponent("running-game.json"), options: .atomic)
        }
        preserve(previousLogURL, as: folder.appendingPathComponent("husk.log"))
        preserve(HuskLog.previousNativeLogURL, as: folder.appendingPathComponent("husk-native.log"))
        preserve(HuskLog.previousSignalLogURL, as: folder.appendingPathComponent("fatal-signal.txt"))
        let url = folder.appendingPathComponent("ChatGPT Crash Report.txt")
        let text = """
        Husk crash diagnostics (automatic; share with ChatGPT)
        =====================================================
        Game     : \(r.game)
        What     : \(r.cause.title)
        Note     : \(r.cause.detail)
        Started  : \(r.when.map { ISO8601DateFormatter().string(from: $0) } ?? "?")
        Husk     : \(info["CFBundleShortVersionString"] as? String ?? "?") (\(info["CFBundleVersion"] as? String ?? "?")) \(info["HuskBuildCommit"] as? String ?? "")
        Run build: \(r.context["build"] as? String ?? "UNAVAILABLE")
        Device   : \(HuskLog.deviceModel), \(UIDevice.current.systemName) \(UIDevice.current.systemVersion)
        Bundle   : \(Bundle.main.bundleIdentifier ?? "?")
        Session  : \(r.context["session"] as? String ?? "?")
        Evidence : A missing fatal signal does NOT prove the game itself crashed.
                   Jetsam, watchdog, process kill, and LiveContainer host termination
                   may require an iOS Analytics incident report to identify.
                   SIGTRAP/SIGBUS belong to the JIT handler and are not recorded
                   by Husk's generic fatal-signal handler.

        ---- game lifecycle and environment ----
        \(contextText)

        ---- dedicated fatal signal (if captured) ----
        \(readTail(HuskLog.previousSignalLogURL, bytes: 8192))

        ---- previous Husk log (last 1 MiB; full saved separately) ----
        \(readTail(previousLogURL, bytes: 1024 * 1024))

        ---- previous native stderr (last 1 MiB; full saved separately) ----
        \(readTail(HuskLog.previousNativeLogURL, bytes: 1024 * 1024))

        Additional files next to this report: running-game.json, husk.log,
        husk-native.log, fatal-signal.txt (when available).
        Nothing was uploaded automatically.
        """
        do {
            try text.write(to: url, atomically: true, encoding: .utf8)
            pruneArchives(keeping: folder)
            return url
        } catch {
            HuskLog.log("crash", "could not save persistent report: \(error)")
            return nil
        }
    }
}

/// The sheet shown at launch after a game ended Husk.
struct CrashReportSheet: View {
    let report: CrashReport.Report
    @Environment(\.dismiss) private var dismiss
    @State private var file: URL?
    @State private var reporting: CompatSubject?

    /// The game, for a report to the compatibility list.
    private var subject: CompatSubject? {
        guard let app = TranslationLayerStore.shared.apps.first(where: { $0.id == report.appID }), let pkg = app.packageName else { return nil }
        return CompatSubject(package: pkg, name: app.label, isGame: LibraryItem.game(app).isGame, iconPath: app.iconPath,
                             crash: "\(report.cause.title). \(report.cause.detail)")
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    HStack(spacing: 14) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.system(size: 30)).foregroundStyle(.orange)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(report.cause.title).font(.title3.weight(.semibold))
                            Text(report.game).foregroundStyle(.secondary)
                        }
                    }
                    Text(report.cause.detail).font(.callout)

                    if !report.excerpt.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Last lines").font(.footnote.weight(.semibold)).foregroundStyle(.secondary)
                            Text(report.excerpt.joined(separator: "\n"))
                                .font(.system(size: 10.5, design: .monospaced))
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(10)
                                .background(Color(.secondarySystemBackground), in: RoundedRectangle(cornerRadius: 10))
                        }
                    }

                    if let file {
                        HuskShareLink(item: file) {
                            Label("Share Report", systemImage: "square.and.arrow.up")
                                .frame(maxWidth: .infinity).padding(.vertical, 6)
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    if let subject {
                        Button { reporting = subject } label: {
                            Label("Report to the Compatibility List", systemImage: "list.bullet.clipboard")
                                .frame(maxWidth: .infinity).padding(.vertical, 6)
                        }
                        .buttonStyle(.bordered)
                    }
                    Text("Automatically saved in Files > Husk > Crash Reports (or the LiveContainer guest Documents folder). Additional native and Husk logs are kept beside this report. Nothing is uploaded unless you share it.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                .padding(20)
            }
            .navigationTitle("Crash Report")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
        .task { file = CrashReport.writeReport(report) }
        .sheet(item: $reporting) { CompatReportSheet(subject: $0) }
    }
}
