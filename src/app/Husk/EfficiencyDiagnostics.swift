// SPDX-License-Identifier: GPL-2.0-or-later
import SwiftUI
import UIKit
import Metal
#if canImport(MetalFX)
import MetalFX
#endif

/// Process-scoped diagnostics, including LiveContainer host work. No GPU/power inference.
@MainActor
final class EfficiencyDiagnostics: ObservableObject {
    static let shared = EfficiencyDiagnostics()
    @Published private(set) var running = false
    @Published var interrupted = false
    @Published var exporting = false
    @Published private(set) var canExport = false
    @Published var message = "Monitoring is off"
    @Published var files: [URL] = []
    private var timer: Timer?
    private var observers: [NSObjectProtocol] = []
    private var metadata: [String: Any] = [:]
    private var samples: [[String: Any]] = [], windows: [[String: Any]] = [], events: [[String: Any]] = []
    private var origin = 0.0, windowAt = 0.0, lastCPUAt = 0.0, lastCPU = -1.0, lastMemoryAt = -10.0, lastBatteryAt = -30.0
    private var excludedAt: Double?, excludedReason = "", exclusions: [[String: Any]] = []
    private var dropped = 0, previousBatteryMonitoring = false
    private var gameVisible = false
    private var panelVisible = false
    @Published var phase = "Unmarked"
    private var attached: [String: Any] = [:]
    private var lastBattery: (Double, Int)?
    private var battery = EfficiencyMath.Battery()
    private var environment: [String: Any] = [:]
    private var stoppedReport: [String: Any]?

    private var now: Double { tl_em_clock() }
    private func append(_ row: [String: Any], to array: inout [[String: Any]], limit: Int) {
        if array.count < limit { array.append(row) } else { dropped += 1 }
    }
    private func event(_ type: String, _ detail: String) {
        append(EfficiencyMath.eventFields(type: type, detail: detail, recorded: now, origin: origin), to: &events, limit: 2048)
    }
    func attach(_ configuration: [String: Any]) {
        attached = configuration
        if running { metadata["launch_configuration"] = attached; event("launch_configuration", "Actual launch values captured; selected settings may require restart") }
    }
    func visible(_ value: Bool) { gameVisible = value; refreshExclusion() }
    func panel(_ value: Bool) { panelVisible = value; refreshExclusion() }
    func markPhase(_ value: String) {
        phase = value
        if running { event("phase", value) }
    }
    func setInterrupted(_ value: Bool) { interrupted = value; refreshExclusion() }

    func start() {
        guard !running, !exporting else { return }
        samples = []; windows = []; events = []; exclusions = []; files = []; dropped = 0
        stoppedReport = nil; canExport = false; origin = now; windowAt = origin; lastCPUAt = origin; lastCPU = -1
        lastMemoryAt = origin - 10; lastBatteryAt = origin - 30; excludedAt = nil; excludedReason = ""
        lastBattery = nil; battery = EfficiencyMath.Battery(); environment = [:]
        interrupted = false; phase = "Unmarked"
        let device = UIDevice.current
        previousBatteryMonitoring = device.isBatteryMonitoringEnabled; device.isBatteryMonitoringEnabled = true
        var system = utsname(); uname(&system)
        let machineSize = MemoryLayout.size(ofValue: system.machine)
        let model = withUnsafePointer(to: &system.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: machineSize) { String(cString: $0) }
        }
        var metalCapabilities: [String: Any] = ["gpu_execution_measurement": "UNAVAILABLE: bundled Vulkan interface exposes no completed Metal command buffers",
                                                 "metalfx_integration": "M9 research; no upscaling implemented"]
        if let metalDevice = MTLCreateSystemDefaultDevice() {
            metalCapabilities["device_name"] = metalDevice.name
            #if canImport(MetalFX)
            if #available(iOS 16.0, *) {
                metalCapabilities["metalfx_spatial_supported"] = MTLFXSpatialScalerDescriptor.supportsDevice(metalDevice)
            } else { metalCapabilities["metalfx_spatial_status"] = "UNAVAILABLE: iOS 16 required" }
            #else
            metalCapabilities["metalfx_spatial_status"] = "UNAVAILABLE: SDK has no MetalFX"
            #endif
        }
        metadata = ["session_id": UUID().uuidString, "started_utc": ISO8601DateFormatter().string(from: Date()),
                    "monotonic_origin_seconds": origin, "device_identifier": model,
                    "os": device.systemVersion, "processor_count": ProcessInfo.processInfo.processorCount,
                    "physical_memory_bytes": ProcessInfo.processInfo.physicalMemory,
                    "build_sha": Bundle.main.object(forInfoDictionaryKey: "HuskBuildCommit") as? String ?? "UNAVAILABLE",
                    "build_date": Bundle.main.object(forInfoDictionaryKey: "HuskBuildDate") as? String ?? "UNAVAILABLE",
                    "launch_configuration": attached, "metal_capabilities": metalCapabilities,
                    "process_scope": "Husk/LiveContainer host process; not isolated guest-game utilisation"]
        tl_em_start(); running = true; refreshExclusion(); event("phase", phase); sample()
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.sample() }
        }
        timer?.tolerance = 0.2
        let nc = NotificationCenter.default
        for name in [UIApplication.willResignActiveNotification, UIApplication.didBecomeActiveNotification,
                     UIDevice.batteryLevelDidChangeNotification, UIDevice.batteryStateDidChangeNotification,
                     ProcessInfo.thermalStateDidChangeNotification, UIScreen.brightnessDidChangeNotification] {
            observers.append(nc.addObserver(forName: name, object: nil, queue: .main) { [weak self] note in
                Task { @MainActor in
                    guard let self, self.running else { return }
                    // willResign arrives before applicationState changes.
                    if note.name == UIApplication.willResignActiveNotification { self.transitionExclusion("application inactive") }
                    else { self.refreshExclusion() }
                    self.sample()
                }
            })
        }
        message = "Lightweight monitoring active; energy benefit unverified"
    }
    private func refreshExclusion() {
        guard running else { return }
        let reason = UIApplication.shared.applicationState != .active ? "application inactive" :
            !gameVisible ? "game view not attached" : panelVisible ? "diagnostics panel" : interrupted ? "manual interruption" : ""
        transitionExclusion(reason)
    }
    private func transitionExclusion(_ reason: String) {
        guard reason != excludedReason else { return }
        let t = now
        if let start = excludedAt {
            append(["start": start - origin, "end": t - origin, "reason": excludedReason], to: &exclusions, limit: 2048)
        }
        excludedReason = reason; excludedAt = reason.isEmpty ? nil : t
        tl_em_exclude(!reason.isEmpty)
        lastCPU = -1; battery.resetAnchor()
        event("exclusion", reason.isEmpty ? "included gameplay resumed" : reason)
    }
    private func stats(_ s: tl_em_stats) -> [String: Any] {
        var calls = s.host_calls, times = s.host_ns
        let callList = withUnsafeBytes(of: &calls) { Array($0.bindMemory(to: UInt64.self)) }
        let timeList = withUnsafeBytes(of: &times) { Array($0.bindMemory(to: UInt64.self)) }
        return ["interval_count": s.intervals, "interval_seconds": s.interval_seconds,
                "host_cadence_fps": s.interval_seconds > 0 ? Double(s.intervals) / s.interval_seconds : NSNull(),
                "p50_ms": s.intervals > 0 ? s.p50_ms : NSNull(), "p95_ms": s.intervals > 0 ? s.p95_ms : NSNull(),
                "p99_ms": s.intervals > 0 ? s.p99_ms : NSNull(), "worst_ms": s.intervals > 0 ? s.worst_ms : NSNull(),
                "above_20_ms": s.above20, "above_33_333333_ms": s.above33, "above_50_ms": s.above50,
                "discontinuities": s.discontinuities, "host_calls": callList, "host_ns": timeList,
                "slow_pipeline_calls": s.slow_pipeline_calls, "worst_pipeline_ns": s.worst_pipeline_ns,
                "dropped_collector_records": s.dropped,
                "dropped_frame_intervals_cumulative": s.dropped_frames,
                "dropped_host_records_cumulative": s.dropped_host,
                "dropped_events_cumulative": s.dropped_events,
                "unhistogrammed_interval_seconds_cumulative": Double(s.lost_frame_ns) / 1e9,
                "worst_unhistogrammed_interval_ms_cumulative": Double(s.lost_frame_max_ns) / 1e6,
                "frame_distribution_complete": s.dropped_frames == 0, "swapchain_width": s.width, "swapchain_height": s.height]
    }
    private func collectWindow() {
        var s = tl_em_stats(); tl_em_snapshot(false, &s)
        var row = stats(s); row["start"] = windowAt - origin; row["end"] = now - origin
        append(row, to: &windows, limit: 1440); windowAt = now
    }
    private func sample(forceBattery: Bool = false) {
        guard running else { return }
        tl_pi_report()
        let t = now, memory = t - lastMemoryAt >= 10
        var p = tl_em_process(); tl_em_process_sample(memory, &p)
        var row: [String: Any] = ["t": t - origin, "excluded": !excludedReason.isEmpty,
                                  "cpu_seconds": p.cpu_seconds >= 0 ? p.cpu_seconds : NSNull(), "phase": phase, "cpu_sample_elapsed_seconds": t - lastCPUAt]
        row["process_cpu_percent_one_core"] = EfficiencyMath.cpuPercent(
            previous: lastCPU, current: p.cpu_seconds, elapsed: t - lastCPUAt,
            included: excludedReason.isEmpty).map { $0 as Any } ?? NSNull()
        lastCPU = excludedReason.isEmpty ? p.cpu_seconds : -1; lastCPUAt = t
        if memory {
            row["footprint_bytes"] = p.footprint_bytes >= 0 ? p.footprint_bytes : NSNull()
            row["jetsam_headroom_bytes"] = p.jetsam_bytes >= 0 ? p.jetsam_bytes : NSNull()
            lastMemoryAt = t
        }
        let d = UIDevice.current, level = Double(UIDevice.current.batteryLevel), state = d.batteryState.rawValue
        if forceBattery || t - lastBatteryAt >= 30 || lastBattery?.0 != level || lastBattery?.1 != state {
            row["battery_fraction"] = level >= 0 ? level : NSNull(); row["battery_state"] = state
            battery.sample(time: t, level: level, unplugged: state == UIDevice.BatteryState.unplugged.rawValue,
                           included: excludedReason.isEmpty)
            lastBattery = (level, state); lastBatteryAt = t
        }
        let env: [String: Any] = ["thermal_classification": ProcessInfo.processInfo.thermalState.rawValue,
                                  "low_power_mode": ProcessInfo.processInfo.isLowPowerModeEnabled,
                                  "brightness": Double(UIScreen.main.brightness),
                                  "maximum_refresh_hz": UIScreen.main.maximumFramesPerSecond,
                                  "orientation": d.orientation.rawValue]
        if !NSDictionary(dictionary: env).isEqual(to: environment) { event("environment", String(describing: env)); environment = env }
        row["environment"] = env
        append(row, to: &samples, limit: 7200)
        drainEvents()
        if t - windowAt >= 10 { collectWindow() }
    }
    private func drainEvents() {
        var e = tl_em_event()
        while tl_em_pop(&e) {
            let text = withUnsafePointer(to: &e.text) { p in
                p.withMemoryRebound(to: CChar.self, capacity: 512) { String(cString: $0) }
            }
            append(EfficiencyMath.eventFields(type: "runtime", detail: text, recorded: e.monotonic_seconds, origin: origin), to: &events, limit: 2048)
        }
    }
    func stop() {
        guard running else { return }
        sample(forceBattery: true); tl_em_stop(); drainEvents(); collectWindow()
        if let start = excludedAt { append(["start": start - origin, "end": now - origin, "reason": excludedReason], to: &exclusions, limit: 2048) }
        timer?.invalidate(); timer = nil
        observers.forEach { NotificationCenter.default.removeObserver($0) }; observers = []
        UIDevice.current.isBatteryMonitoringEnabled = previousBatteryMonitoring
        var total = tl_em_stats(); tl_em_snapshot(true, &total)
        stoppedReport = ["schema_version": 2, "metadata": metadata, "duration_seconds": now - origin,
                         "summary": stats(total), "samples": samples, "windows": windows, "events": events, "exclusions": exclusions,
                         "battery_drain_pp_per_hour_estimated": battery.rate.map { $0 as Any } ?? NSNull(),
                         "battery_estimate_status": battery.status,
                         "battery_included_sample_count": battery.sampleCount,
                         "battery_observed_drain_percentage_points": battery.drain,
                         "battery_first_included_fraction": battery.firstLevel.map { $0 as Any } ?? NSNull(),
                         "battery_last_included_fraction": battery.lastLevel.map { $0 as Any } ?? NSNull(),
                         "battery_estimate_observed_seconds": battery.seconds, "dropped_export_records": dropped,
                         "metric_labels": ["host_cadence_cpu_memory_battery_thermal": "MEASURED (process/API scope)",
                                           "histogram_percentiles_battery_drain": "ESTIMATED",
                                           "gpu_execution_displayed_frames_peak_footprint_cache_hits": "UNAVAILABLE",
                                           "electrical_power_chip_temperature_surface_temperature": "EXTERNAL"],
                         "limitations": ["0.1 ms upper-bin nearest-rank percentiles; >=1 s overflow uses exact worst as conservative bound",
                                          "Host API stages: acquire, submit, present, sleep, graphics creation, compute creation; durations overlap",
                                          "Vulkan host cadence is not displayed-frame timing; no frame source for non-Vulkan games",
                                          "No measured watts, GPU execution, degrees Celsius or energy saving",
                                          "CPU includes host/LiveContainer work; 100% = one logical CPU",
                                          "Driver phase counters remain in attempt log if separately enabled",
                                          "Cache feedback may be unavailable; partial pipeline signatures are not cache keys",
                                          "Frame ring is separate from host/event recording; lost intervals and record categories are disclosed",
                                          "Monitoring overhead and physical-device correctness remain unverified"]]
        running = false; canExport = true; excludedAt = nil; message = "Stopped; ready to export"
    }
    func export() {
        guard !running, !exporting, let report = stoppedReport else { return }
        exporting = true; message = "Exporting…"
        // Immutable value snapshot, serialization and disk I/O away from rendering/main thread.
        DispatchQueue.global(qos: .utility).async {
            do {
                let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                    .appendingPathComponent("EfficiencyTests").appendingPathComponent(UUID().uuidString)
                try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
                let json = dir.appendingPathComponent("diagnostics.json"), md = dir.appendingPathComponent("report.md")
                try EfficiencyMath.json(report).write(to: json, options: .atomic)
                let summary = report["summary"] as? [String: Any] ?? [:], meta = report["metadata"] as? [String: Any] ?? [:]
                let rows = report["samples"] as? [[String: Any]] ?? []
                let cpu = rows.compactMap { $0["process_cpu_percent_one_core"] as? Double }
                let footprints = rows.compactMap { $0["footprint_bytes"] as? Int64 }
                let thermal = Set(rows.compactMap { ($0["environment"] as? [String: Any])?["thermal_classification"] as? Int }).sorted()
                let text = """
                # Husk efficiency test
                Build: \(meta["build_sha"] ?? "UNAVAILABLE")
                Device: \(meta["device_identifier"] ?? "UNAVAILABLE"); OS: \(meta["os"] ?? "UNAVAILABLE")
                Configuration: \(meta["launch_configuration"] ?? "UNAVAILABLE")
                Duration: \(report["duration_seconds"] ?? 0) seconds; excluded periods are preserved in JSON.

                MEASURED host cadence: \(summary["host_cadence_fps"] ?? "UNAVAILABLE") FPS
                ESTIMATED interval p50/p95/p99: \(summary["p50_ms"] ?? "UNAVAILABLE") / \(summary["p95_ms"] ?? "UNAVAILABLE") / \(summary["p99_ms"] ?? "UNAVAILABLE") ms
                MEASURED worst interval: \(summary["worst_ms"] ?? "UNAVAILABLE") ms
                Intervals >20/33.33/50 ms: \(summary["above_20_ms"] ?? 0) / \(summary["above_33_333333_ms"] ?? 0) / \(summary["above_50_ms"] ?? 0)
                Slow pipeline calls: \(summary["slow_pipeline_calls"] ?? 0); worst host call: \(summary["worst_pipeline_ns"] ?? 0) ns
                Process CPU maximum sampled activity: \(cpu.max().map { String(format: "%.2f%%", $0) } ?? "UNAVAILABLE") (100% = one logical CPU, not whole-device usage)
                Maximum observed footprint: \(footprints.max().map { String(format: "%.3f GiB", Double($0) / 1073741824) } ?? "UNAVAILABLE") (not actual peak)
                Thermal classifications observed: \(thermal)
                Battery status: \(report["battery_estimate_status"] ?? "UNAVAILABLE")
                Included battery samples/span: \(report["battery_included_sample_count"] ?? 0) / \(report["battery_estimate_observed_seconds"] ?? 0) seconds
                Observed battery decrease: \(report["battery_observed_drain_percentage_points"] ?? 0) percentage points
                ESTIMATED unplugged drain: \(report["battery_drain_pp_per_hour_estimated"] ?? "UNAVAILABLE") percentage points/hour (coarse).
                Dropped collector/export records: \(summary["dropped_collector_records"] ?? 0) / \(report["dropped_export_records"] ?? 0)

                Frame distribution complete: \(summary["frame_distribution_complete"] ?? false)
                Dropped frame/host/event records: \(summary["dropped_frame_intervals_cumulative"] ?? 0) / \(summary["dropped_host_records_cumulative"] ?? 0) / \(summary["dropped_events_cumulative"] ?? 0)
                CPU/memory/battery/thermal samples, timestamped runtime events, phase markers and exclusions: diagnostics.json.
                UNAVAILABLE: actual displayed frames, GPU execution, peak footprint and verified pipeline cache hits.
                EXTERNAL: electrical power and numerical physical temperature. Thermal state is a classification.
                No measured energy improvement. Monitoring overhead and device correctness need validation.
                """
                try text.write(to: md, atomically: true, encoding: .utf8)
                DispatchQueue.main.async { self.files = [md, json]; self.exporting = false; self.message = "Saved report and JSON in Files > Husk > EfficiencyTests" }
            } catch {
                DispatchQueue.main.async { self.exporting = false; self.message = "Export failed: \(error.localizedDescription)" }
            }
        }
    }
}

struct EfficiencyDiagnosticsView: View {
    @ObservedObject private var monitor = EfficiencyDiagnostics.shared
    @Environment(\.dismiss) private var dismiss
    @State private var sharing = false
    var body: some View {
        NavigationView {
            Form {
                Section {
                    Text(monitor.message)
                    Button("Start lightweight test") { monitor.start() }.disabled(monitor.running || monitor.exporting)
                    Picker("Phase marker", selection: Binding(get: { monitor.phase }, set: { monitor.markPhase($0) })) {
                        ForEach(["Unmarked", "Loading", "Menu", "Gameplay", "First-use effect", "Repeated effect"], id: \.self) { Text($0).tag($0) }
                    }.disabled(!monitor.running)
                    Toggle("Exclude manual interruption", isOn: Binding(get: { monitor.interrupted }, set: { monitor.setInterrupted($0) }))
                        .disabled(!monitor.running)
                    Button("Stop test") { monitor.stop() }.disabled(!monitor.running)
                    Button("Export report and JSON") { monitor.export() }.disabled(!monitor.canExport || monitor.running || monitor.exporting)
                    Button("Share exported files") { sharing = true }.disabled(monitor.files.isEmpty)
                } header: { Text("Performance & Efficiency Diagnostics") }
                Section {
                    Text("Return to gameplay after starting. This panel, background time and detached game views are excluded. Mark other interruptions explicitly. Tests remain in memory until stopped/exported; export before closing Husk.")
                    Text("Lightweight monitoring changes no graphics settings. Detailed Driver Profiling remains a separate option requiring restart; leave it off for energy comparisons.")
                    Text("CPU is process-scoped. Thermal state is not temperature. GPU execution and watts require external instrumentation. Monitoring overhead has not yet been measured on device.")
                }
            }
            .navigationTitle("Efficiency Test")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
        .onAppear { monitor.panel(true) }.onDisappear { monitor.panel(false) }
        .sheet(isPresented: $sharing) { EfficiencyShare(items: monitor.files) }
    }
}
private struct EfficiencyShare: UIViewControllerRepresentable {
    let items: [URL]
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: items, applicationActivities: nil) }
    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
