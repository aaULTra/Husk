// SPDX-License-Identifier: GPL-2.0-or-later
import SwiftUI
import UIKit
import Metal
import QuartzCore
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
    private var gpuExcludedStart: (Double, Double)?
    private var dropped = 0, previousBatteryMonitoring = false
    private var gameVisible = false
    private var panelVisible = false
    @Published var phase = "Unmarked"
    @Published var gpuSampling = false
    @Published var cpuThreadSampling = false
    @Published var componentSampling = false
    @Published var displaySampling = false
    private var lastThreadAt = -10.0
    private final class GPUWindow {
        var intervals: [(Double, Double)] = []
        var count = 0
        var duration = 0.0
        var roleCounts: [String: Int] = [:]
        var roleDurations: [String: Double] = [:]
    }
    private var gpuWindows: [Double: GPUWindow] = [:]
    private var gpuAggregateDrops = 0
    private var gpuRows: [[String: Any]] = []
    private var gpuExportDrops = 0
    private var attached: [String: Any] = [:]
    private var lastBattery: (Double, Int)?
    private var battery = EfficiencyMath.Battery()
    private var environment: [String: Any] = [:]
    @Published private(set) var nativePreparing = false
    @Published private(set) var archiveMessage = "Native archive is off or not yet inspected"
    @Published private(set) var archiveFiles: [URL] = []
    @Published private(set) var archiveInspectionFiles: [URL] = []
    private var archiveInspectionSequence = 0
    private var lastArchiveInspection: [String: Any]?
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
        guard !running, !exporting, !nativePreparing else { return }
        samples = []; windows = []; events = []; exclusions = []; files = []; dropped = 0
        gpuRows = []; gpuExportDrops = 0; gpuWindows = [:]; gpuAggregateDrops = 0; lastThreadAt = now - 10
        stoppedReport = nil; canExport = false; origin = now; windowAt = origin; lastCPUAt = origin; lastCPU = -1
        lastMemoryAt = origin - 10; lastBatteryAt = origin - 30; excludedAt = nil; excludedReason = ""; gpuExcludedStart = nil
        lastBattery = nil; battery = EfficiencyMath.Battery(); environment = [:]
        interrupted = false; phase = "Unmarked"
        let device = UIDevice.current
        previousBatteryMonitoring = device.isBatteryMonitoringEnabled; device.isBatteryMonitoringEnabled = true
        var system = utsname(); uname(&system)
        let machineSize = MemoryLayout.size(ofValue: system.machine)
        let model = withUnsafePointer(to: &system.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: machineSize) { String(cString: $0) }
        }
        var metalCapabilities: [String: Any] = ["gpu_execution_measurement": gpuSampling ? "M3-A opt-in sampled command-buffer GPU timestamps; device validation pending" : "UNAVAILABLE: GPU sampling disabled",
                                                 "metalfx_integration": "M9 default-off experimental spatial path; see spatial_upscaling actual driver counters; device/benefit unverified"]
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
                    "physical_memory_bytes": ProcessInfo.processInfo.physicalMemory, "device_capabilities": EfficiencyDeviceInventory.snapshot(),
                    "build_sha": Bundle.main.object(forInfoDictionaryKey: "HuskBuildCommit") as? String ?? "UNAVAILABLE",
                    "build_date": Bundle.main.object(forInfoDictionaryKey: "HuskBuildDate") as? String ?? "UNAVAILABLE",
                    "launch_configuration": attached, "metal_capabilities": metalCapabilities,
                    "process_scope": "Husk/LiveContainer host process; not isolated guest-game utilisation"]
        metadata["component_sampling_requested"] = componentSampling
        metadata["display_sampling_requested"] = displaySampling
        metadata["cpu_thread_sampling_requested"] = cpuThreadSampling
        tl_vk_display_monitor(displaySampling);
        tl_cp_start(componentSampling); tl_em_start(); tl_em_cpu_work_enable(cpuThreadSampling); tl_pt_monitor(true); tl_gput_native_start(gpuSampling)
        // Bracket a host-clock read with media-clock reads. Raw values remain
        // authoritative; this mapping supports estimated host/GPU correlation.
        metadata["gpu_clock_alignment"] = gpuClockAlignment()
        running = true; refreshExclusion(); tl_vk_display_exclude(!excludedReason.isEmpty); tl_cp_exclude(!excludedReason.isEmpty); event("phase", phase); sample()
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
        var mediaBefore = 0.0, mediaAfter = 0.0
        tl_vk_display_exclude(!reason.isEmpty)
        tl_cp_exclude(!reason.isEmpty)
        tl_em_exclude(!reason.isEmpty)
        tl_gput_native_exclude(!reason.isEmpty, &mediaBefore, &mediaAfter)
        if let start = excludedAt {
            append(exclusionRow(start, t, mediaBefore, mediaAfter), to: &exclusions, limit: 2048)
        }
        excludedReason = reason; excludedAt = reason.isEmpty ? nil : t
        gpuExcludedStart = reason.isEmpty ? nil : (mediaBefore, mediaAfter)
        lastCPU = -1; battery.resetAnchor()
        event("exclusion", reason.isEmpty ? "included gameplay resumed" : reason)
    }
    private func gpuClockAlignment() -> [String: Any] {
        let a = CACurrentMediaTime(), host = now, b = CACurrentMediaTime()
        return ["media_anchor_seconds": (a + b) / 2, "monotonic_anchor_seconds": host,
                "read_bracket_seconds": b - a,
                "mapping": "ESTIMATED host/GPU correlation; direct exclusion media brackets take precedence; end anchor exposes drift"]
    }
    private func exclusionRow(_ start: Double, _ end: Double, _ mediaBefore: Double, _ mediaAfter: Double) -> [String: Any] {
        var row: [String: Any] = ["start": start - origin, "end": end - origin, "reason": excludedReason]
        if let begin = gpuExcludedStart {
            row["gpu_media_start_before_seconds"] = begin.0; row["gpu_media_start_after_seconds"] = begin.1
            row["gpu_media_end_before_seconds"] = mediaBefore; row["gpu_media_end_after_seconds"] = mediaAfter
        }
        return row
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
                "frame_distribution_complete": s.dropped_frames == 0,
                "guest_yield_calls_cumulative": s.guest_yield_calls, "swapchain_width": s.width, "swapchain_height": s.height]
    }
    private func collectWindow() {
        var s = tl_em_stats(); tl_em_snapshot(false, &s)
        var row = stats(s); row["component_sampling"] = componentReport(); row["driver_phases"] = driverPhaseReport(); row["start"] = windowAt - origin; row["end"] = now - origin
        append(row, to: &windows, limit: 1440); windowAt = now
    }
    private func collectGPU() {
        var record = tl_gput_record()
        while tl_gput_pop(&record) {
            let role = ["unknown", "acquire", "submit", "present", "other"][min(Int(record.kind), 4)]
            if gpuWindows[record.sample_start] != nil || gpuWindows.count < 512 {
                let window = gpuWindows[record.sample_start] ?? GPUWindow()
                let lo = max(record.gpu_start, record.sample_start), hi = min(record.gpu_end, record.sample_end)
                if hi > lo { window.intervals.append((lo, hi)) }
                window.count += 1; window.duration += record.gpu_end - record.gpu_start
                window.roleCounts[role, default: 0] += 1
                window.roleDurations[role, default: 0] += record.gpu_end - record.gpu_start
                gpuWindows[record.sample_start] = window
            } else { gpuAggregateDrops += 1 }
            if gpuRows.count >= 16384 { gpuExportDrops += 1; continue }
            gpuRows.append(["command_buffer_role": role, "gpu_start_media_seconds": record.gpu_start, "gpu_end_media_seconds": record.gpu_end,
                            "completed_media_seconds": record.completed, "completion_after_gpu_end_seconds": max(0, record.completed - record.gpu_end),
                            "sample_start_media_seconds": record.sample_start, "sample_end_media_seconds": record.sample_end,
                            "queue_id": record.queue, "phase_at_collection": phase,
                            "recorded_t": now - origin, "plan_ids": ["M3", "GPU-01"],
                            "subsystem": "gpu_execution", "benefit_validation": "unverified"])
        }
    }
    private func gpuWindowReport() -> [[String: Any]] {
        gpuWindows.sorted { $0.key < $1.key }.map { start, w in
            ["sample_start_media_seconds": start, "sample_end_media_seconds": start + 1,
             "valid_records": w.count, "buffer_duration_sum_seconds": w.duration,
             "sample_clipped_interval_union_seconds": EfficiencyMath.intervalUnion(w.intervals),
             "command_buffer_role_counts": w.roleCounts, "role_overlapping_gpu_duration_seconds": w.roleDurations,
             "scope": "All drained valid records in this bounded window, including those beyond raw export cap; partial coverage, overlapping buffer durations, not per-frame GPU or watts"]
        }
    }
    private func gpuReport() -> [String: Any] {
        var s = tl_gput_stats(); tl_gput_snapshot(&s)
        let status = !s.requested ? "UNAVAILABLE: disabled" : s.completed > 0 ?
            "MEASURED: sampled command-buffer GPU intervals; partial coverage" : s.hooked_queues == 0 ?
            "UNAVAILABLE: no compatible registered game queue" : "UNAVAILABLE: no valid sampled GPU timestamps"
        return ["status": status, "requested": s.requested, "registered_queues": s.registered_queues,
                "hooked_queues": s.hooked_queues, "hook_failures": s.hook_failures,
                "attached_handlers": s.attached, "valid_records": s.completed, "invalid_timestamps": s.invalid,
                "command_buffer_errors": s.errors, "outside_sample_window": s.outside,
                "stale_or_excluded_completions": s.stale, "unresolved_handlers_at_snapshot": s.pending,
                "dropped_records_or_capture_attempts": s.dropped, "dropped_export_records": gpuExportDrops,
                "media_origin_seconds": s.media_origin, "sample_period_seconds": 10, "sample_width_seconds": 1,
                "observed_interval_union_seconds": EfficiencyMath.gpuIntervalUnion(gpuRows),
                "scope": "Known MoltenVK game queues; factory-created buffers only; sample-bound clipped union is partial, not utilisation or per-frame GPU time",
                "clock": "Metal GPU timestamps and sample bounds use media clock; report event t uses a separate monotonic origin",
                "aggregate_records": gpuWindows.values.reduce(0) { $0 + $1.count },
                "aggregate_window_count": gpuWindows.count, "dropped_aggregate_records": gpuAggregateDrops,
                "all_window_sample_clipped_union_seconds": gpuWindows.values.reduce(0.0) { $0 + EfficiencyMath.intervalUnion($1.intervals) },
                "overhead_validation": "pending", "plan_ids": ["M3", "GPU-01"]]
    }
    private func workerReport(includeObservations: Bool = true) -> [String: Any] {
        var s = tl_worker_summary(); tl_thread_policy_summary(&s)
        let reason = withUnsafePointer(to: &s.waiting_reason) { $0.withMemoryRebound(to: CChar.self, capacity: 96) { String(cString: $0) } }
        var observations: [[String: Any]] = []
        if includeObservations {
            var records = Array(repeating: tl_worker_observation(), count: 64)
            let count = records.withUnsafeMutableBufferPointer { tl_thread_policy_observations($0.baseAddress, UInt32($0.count)) }
            observations = records.prefix(Int(count)).map { value in
                var v = value
                let name = withUnsafePointer(to: &v.name) { $0.withMemoryRebound(to: CChar.self, capacity: 64) { String(cString: $0) } }
                return ["observer_thread_id": v.identity, "name": name, "role": v.role, "mode": v.mode,
                        "revision": v.revision, "observed_t": v.observed_monotonic - origin,
                        "before_qos": v.before_qos, "after_qos": v.query_result == 0 ? v.after_qos as Any : NSNull(),
                        "query_result": v.query_result, "set_result": v.set_result, "policy_changed": v.changed]
            }
        }
        return ["requested_mode": s.requested_mode, "active_mode": s.active_mode,
                "revision": s.revision, "capacity_hint": s.capacity_hint, "reserved_normal_worker_budget": s.fast_worker_budget,
                "trial_requested": s.trial_requested, "admissions_since_launch": s.admissions,
                "rollback_requests_since_launch": s.rollback_requests, "caps_applied_since_launch": s.caps_applied,
                "restores_applied_since_launch": s.restores_applied, "query_failures_since_launch": s.query_failures,
                "set_failures_since_launch": s.set_failures, "dropped_observations_since_launch": s.dropped_observations,
                "relative_trial": s.relative_trial, "admission_baseline_fps": s.baseline_fps,
                "admission_baseline_p95_ms": s.baseline_p95_ms,
                "relative_guard_limits": "20s stable >=55 FPS / p95<=21.5ms; rollback >2% FPS loss or >0.5ms p95 growth, 6 >22ms frames, >50ms frame; unchanged thermal/pipeline guards",
                "stable_seconds": s.stable_seconds, "cooldown_remaining_seconds": s.cooldown_remaining_seconds,
                "waiting_reason": reason, "last_observed_workers": observations,
                "scope": "Last self-checkpoint observations since activation; not live threads, core residency, effective QoS overrides or per-worker energy",
                "plan_ids": ["M7", "WORK-01", "WORK-02"], "benefit_validation": "unverified"]
    }
    private func sample(forceBattery: Bool = false) {
        guard running else { return }
        tl_pi_report(); collectGPU()
        let t = now, memory = t - lastMemoryAt >= 10
        var p = tl_em_process(); tl_em_process_sample(memory, &p)
        var row: [String: Any] = ["t": t - origin, "excluded": !excludedReason.isEmpty,
                                  "cpu_seconds": p.cpu_seconds >= 0 ? p.cpu_seconds : NSNull(), "phase": phase, "cpu_sample_elapsed_seconds": t - lastCPUAt]
        row["process_cpu_percent_one_core"] = EfficiencyMath.cpuPercent(
            previous: lastCPU, current: p.cpu_seconds, elapsed: t - lastCPUAt,
            included: excludedReason.isEmpty).map { $0 as Any } ?? NSNull()
        if cpuThreadSampling && t - lastThreadAt >= 10 {
            let threadReadStarted = now
            var records = Array(repeating: tl_em_thread(), count: 128), details = tl_em_thread_stats()
            let count = records.withUnsafeMutableBufferPointer { tl_em_thread_sample($0.baseAddress, UInt32($0.count), &details) }
            let threads: [[String: Any]] = records.prefix(Int(count)).map { value in
                var record = value
                let name = withUnsafePointer(to: &record.name) { $0.withMemoryRebound(to: CChar.self, capacity: 64) { String(cString: $0) } }
                return ["thread_id": record.identity, "name": name, "user_seconds": record.user_seconds,
                        "system_seconds": record.system_seconds, "run_state": record.run_state]
            }
            row["cpu_threads"] = ["status": details.result == 0 ? "MEASURED: cumulative process-thread counters" : "UNAVAILABLE: thread enumeration failed",
                "threads": threads, "enumerated": details.enumerated, "scanned": details.scanned,
                "returned": details.returned, "failures": details.failures, "truncated": details.truncated,
                "mach_result": details.result, "read_duration_seconds": now - threadReadStarted, "plan_ids": ["M3", "M7", "M8"],
                "scope": "At most 128 returned / 256 scanned, about 10s; includes host threads, no P/E placement, electrical power or exited-thread accounting"]
            lastThreadAt = t
        }
        lastCPU = excludedReason.isEmpty ? p.cpu_seconds : -1; lastCPUAt = t
        if memory {
            row["footprint_bytes"] = p.footprint_bytes >= 0 ? p.footprint_bytes : NSNull()
            row["process_lifetime_peak_footprint_bytes"] = p.peak_bytes >= 0 ? p.peak_bytes : NSNull()
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
        row["worker_controller"] = workerReport(includeObservations: false).filter { $0.key != "last_observed_workers" }
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
    private func renderInventory() -> [String: Any] {
        var groups = Array(repeating: tl_ri_group(), count: 256), s = tl_ri_stats()
        let count = groups.withUnsafeMutableBufferPointer { tl_ri_snapshot($0.baseAddress, UInt32($0.count), &s) }
        let rows: [[String: Any]] = groups.prefix(Int(count)).map { g in
            ["kind": g.kind == 0 ? "successful_image_creation_requested_base_fields" : "legacy_renderpass_requested_area",
             "width": g.width, "height": g.height, "depth": g.depth, "vulkan_format": g.format,
             "vulkan_usage": g.usage, "samples": g.samples, "count_since_launch": g.count]
        }
        return ["requested": s.requested, "active": s.active, "observed_image_creations": s.observed_images,
                "observed_legacy_render_areas": s.observed_render_areas, "dropped_observations": s.dropped,
                "dropped_capacity": s.dropped_capacity, "dropped_contention": s.dropped_contention,
                "hash_lookup_probes": s.hash_probes, "retained_asset_groups": s.asset_groups,
                "retained_target_groups": s.target_groups, "retained_area_groups": s.area_groups,
                "capacity_by_category": ["assets": 64, "targets": 96, "areas": 96],
                "groups_since_launch": rows, "plan_ids": ["M9", "GAP-03"],
                "scope": "Requested base fields/legacy render areas since launch; not actual scene/HUD pixels, executed GPU passes, texture identity or replay state; swapchain images and newer renderpass paths may be absent",
                "metalfx_integration": "separate opt-in prototype; requested inventory does not prove internal scene resolution", "benefit_validation": "unverified"]
    }
    private func spatialReport() -> [String: Any] {
        var s = tl_spatial_stats()
        tl_vk_spatial_snapshot(&s)
        var binding = tl_spatial_bindings()
        let bindingAPI = tl_vk_spatial_bindings(&binding)
        let bindings: [String: Any] = ["available": bindingAPI,
            "output_contract_checks_since_driver_launch": bindingAPI ? binding.output_contract_checks as Any : NSNull(),
            "output_rebinds_since_driver_launch": bindingAPI ? binding.output_rebinds as Any : NSNull(),
            "scope": "M9 immutable repeated-drawable binding cache. Different output textures remain validated/rebound. Mechanism counts, not GPU or energy savings."]
        var observed = tl_spatial_observations()
        let observationAPI = tl_vk_spatial_observations(&observed)
        let textures: [String: Any] = ["status": observationAPI && observed.observed_images > 0 ? "MEASURED: actual texture properties at validated encode" : "UNAVAILABLE: no actual texture observation",
            "input_width": observed.input_width, "input_height": observed.input_height,
            "output_width": observed.output_width, "output_height": observed.output_height,
            "input_metal_format": observed.input_format, "output_metal_format": observed.output_format,
            "color_processing_mode": observed.color_processing, "observed_images": observed.observed_images,
            "unsupported_swapchains": observed.unsupported_swapchains,
            "resource_preparation_failures": observed.allocation_failures,
            "encode_validation_failures": observed.encode_validation_failures,
            "scope": "Once per image; actual MetalFX boundary textures, not internal UE scene resolution, displayed pixels or perceptual quality"]
        var build: Any = "UNAVAILABLE: experimental driver absent"
        if let root = Bundle.main.privateFrameworksPath,
           let data = try? Data(contentsOf: URL(fileURLWithPath: root + "/HuskMoltenVK.framework/HuskSpatialBuild.json")),
           let object = try? JSONSerialization.jsonObject(with: data) { build = object }
        return ["driver_build": build, "plan_ids": ["M9", "M3"], "scope": "MEASURED driver configuration/encode calls; successful encode is not proof of displayed quality or energy benefit",
                "configured": s.configured != 0, "live_images": s.live_images,
                "input_width": s.input_width, "input_height": s.input_height,
                "output_width": s.output_width, "output_height": s.output_height,
                "images_created": s.images_created, "encoded_calls": s.encoded, "failures": s.failures,
                "output_binding_reuse": bindings, "texture_observations": textures, "patch": "M9-SPATIAL-v3", "energy_benefit": "UNVERIFIED"]
    }
    private func nativeDisplayReport() -> [String: Any] {
        var info = tl_display_stats(), copied: UInt32 = 0
        var records = Array(repeating: tl_display_record(), count: Int(TL_DISPLAY_CAPACITY))
        let available = records.withUnsafeMutableBufferPointer { tl_vk_display_snapshot(&info, $0.baseAddress, UInt32($0.count), &copied) }
        let histogram: [UInt64] = withUnsafePointer(to: &info.histogram) { pointer in
            pointer.withMemoryRebound(to: UInt64.self, capacity: Int(TL_DISPLAY_BINS)) { Array(UnsafeBufferPointer(start: $0, count: Int(TL_DISPLAY_BINS))) }
        }
        func percentile(_ fraction: Double) -> Any {
            guard info.intervals > 0 else { return NSNull() }
            let wanted = UInt64(ceil(Double(info.intervals) * fraction))
            var count: UInt64 = 0
            for (index, value) in histogram.enumerated() {
                count += value
                if count >= wanted { return index == histogram.count - 1 ? NSNull() : Double(index) / 10 as Any }
            }
            return NSNull()
        }
        let rows: [[String: Any]] = records.prefix(Int(copied)).map { r in
            ["sequence": r.sequence, "swapchain_generation": r.swapchain_generation,
             "raw_drawable_presented_media_ns": r.raw_drawable_ns, "effective_driver_timestamp_ns": r.effective_driver_ns,
             "driver_begin_timestamp_ns": r.begin_driver_ns, "observed_media_ns": r.observed_media_ns,
             "google_present_id": r.google_id, "source": r.source == 1 ? "drawable_presented_time" : "driver_estimate"]
        }
        return ["plan_ids": ["M4", "M6", "M3"], "requested": displaySampling, "available": available,
                "capture_enabled": info.enabled != 0, "excluded": info.excluded != 0, "epoch": info.epoch,
                "attempts": info.attempts, "direct_drawable_events": info.direct_events, "estimated_events": info.estimated_events,
                "invalid_events": info.invalid_events, "boundary_events": info.boundary_events, "contention_drops": info.contention_drops,
                "record_overwrites": info.overwrites, "valid_intervals": info.intervals, "interval_seconds": Double(info.interval_ns) / 1e9,
                "worst_interval_ms": Double(info.worst_interval_ns) / 1e6,
                "above_20_ms": info.above20, "above_33_333333_ms": info.above33, "above_50_ms": info.above50,
                "p50_ms_estimated": percentile(0.5), "p95_ms_estimated": percentile(0.95), "p99_ms_estimated": percentile(0.99),
                "histogram_0_1ms": histogram, "records": rows,
                "scope": "Opt-in callback provenance. Only positive raw CAMetalDrawable.presentedTime enters the interval histogram; driver fallback estimates remain separate. Same swapchain generation, consecutive collected callback attempts and increasing times only. Exclusions/reset/drop/invalid/fallback interrupt continuity; late pre-inclusion callbacks rejected. Full included aggregate survives256-record tail overwrite. Callback delivery/order/completeness and physical visibility are not independently verified; not complete displayed FPS, GPU execution, watts or an energy/frame denominator. Histogram final bucket>51.0ms; percentile in that bucket unavailable. Instrumentation overhead remains unmeasured."]
    }
    private func swapchainBudgetReport() -> [String: Any] {
        var s = tl_sb_stats(); tl_sb_snapshot(&s)
        return ["plan_ids": ["M6", "M8"], "requested_images": s.requested, "original_min_images": s.original_min,
                "selected_min_images": s.selected_min, "caps_available": s.caps_result == 0,
                "surface_min_images": s.surface_min, "surface_max_images": s.surface_max,
                "override_applied": s.override_applied, "surface_eligible": s.eligible,
                "last_create_result": s.create_result, "create_result_available": s.create_completed, "returned_image_count": s.returned_images,
                "returned_image_count_complete": s.images_complete, "image_query_result": s.images_result,
                "create_calls_since_launch": s.create_calls, "override_calls_since_launch": s.override_calls,
                "rejected_overrides_since_launch": s.rejections, "device_registry_drops": s.device_capacity_drops,
                "generation": s.generation, "scope": "Last started swapchain creation/generation and matching native image query; counters since launch. Surface-checked min-image request, no change to extent/mode/ownership. Complete actual count requires a successful image query. Images are not Vulkan frames in flight; no GPU/energy inference. Failed creations are never retried with a retired old swapchain."]
    }
    private func queueExecutionReport() -> [String: Any] {
        var s = tl_queue_options_stats(); tl_queue_options_snapshot(&s)
        return ["plan_ids": ["M6", "M8"], "requested_prefill": s.requested_prefill, "requested_command_buffer_limit": s.requested_limit,
                "environment_applied": s.applied, "environment_error": s.environment_error, "actual_configuration_available": s.observed,
                "configuration_query_result": s.query_result, "actual_synchronous_submission": s.observed ? s.actual_synchronous as Any : NSNull(),
                "actual_prefill": s.observed ? s.actual_prefill as Any : NSNull(), "actual_command_buffer_limit": s.observed ? s.actual_limit as Any : NSNull(),
                "scope": "Launch-time requested controls versus size-checked MoltenVK runtime configuration. Limit bounds native Metal buffers, not Vulkan frames in flight. Environment application alone is not treatment or energy proof."]
    }
    private func initializationWaitReport() -> [String: Any] {
        var s = tl_publication_stats(); tl_publication_snapshot(&s)
        return ["plan_ids": ["M8", "M3"], "requested": s.requested, "wait_entries_since_launch": s.waits,
                "notifications_since_launch": s.wakeups, "fallback_sleep_entries_since_launch": s.fallbacks,
                "scope": "Since launch, including startup/exclusions. Predicate-checked once/object initialization waits only. Ready fast path unchanged. Counts are not CPU, P/E residency or energy savings; no observed waits means no demonstrated opportunity."]
    }
    private func driverPhaseReport() -> [String: Any] {
        var info = tl_dp_info(), phases = Array(repeating: tl_dp_phase(), count: 23)
        let count = phases.withUnsafeMutableBufferPointer { tl_dp_copy($0.baseAddress, UInt32($0.count), &info) }
        let rows: [[String: Any]] = phases.prefix(Int(count)).map { p in
            ["phase_id": p.phase, "component": String(cString: tl_dp_name(p.phase)),
             "new_calls_since_previous_query": p.new_calls, "lifetime_calls": p.total_calls,
             "counter_reset_or_wrap": p.reset, "lifetime_average_ms": p.lifetime_average_ms,
             "latest_event_ms": p.latest_ms, "lifetime_max_ms": p.lifetime_max_ms,
             "new_total_ms_estimated": p.estimated_total_valid ? p.estimated_new_total_ms as Any : NSNull()]
        }
        return ["plan_ids": ["M3", "M8", "M2"], "requested": info.requested,
                "available": info.available, "compatible": info.compatible,
                "query_serial": info.serial, "previous_query_monotonic_ns": info.previous_query_ns,
                "query_monotonic_ns": info.queried_ns, "invalid_phase_values": info.invalid_values,
                "phases": rows, "status": info.available ? "MEASURED driver host-activity counters; ESTIMATED new aggregate duration" : "UNAVAILABLE: profiling off, unsupported ABI, or no accepted query",
                "scope": "Read-only copy of already-collected opt-in MoltenVK1.4.2/private43 sample. Serial/timestamp deduplicate repeated copies. Counters include pre-session/lifecycle/excluded work. First query is lifetime; maxima/averages remain lifetime. New totals subtract average*count and are estimates, unavailable on reset. Activities overlap: never sum; callback latency is not GPU execution, drawable waiting is not electrical power. Heavy profiling remains separate and off by default."]
    }
    private func componentReport() -> [String: Any] {
        let names = ["vulkan_acquire_wrapper", "vulkan_submit_wrapper", "present_wrapper_including_limiter", "graphics_pipeline_wrapper", "compute_pipeline_wrapper", "jni_invoke", "futex_wait_operation", "futex_wake_operation", "once_slow_path_including_initializer"]
        var stats = tl_cp_stats(), rows = Array(repeating: tl_cp_row(), count: Int(TL_CP_COUNT))
        let count = rows.withUnsafeMutableBufferPointer { tl_cp_snapshot($0.baseAddress, UInt32($0.count), &stats) }
        let records: [[String: Any]] = rows.prefix(Int(count)).map { r in
            ["component_id": r.kind, "component": Int(r.kind) < names.count ? names[Int(r.kind)] : "unknown",
             "completed_sampled_calls": r.samples, "sampled_wall_ns": r.wall_ns, "sampled_caller_cpu_ns": r.cpu_ns,
             "worst_sampled_wall_ns": r.worst_wall_ns, "worst_sampled_cpu_ns": r.worst_cpu_ns]
        }
        return ["plan_ids": ["M1", "M3", "M8"], "requested": stats.requested,
                "status": stats.requested ? "MEASURED completed included sampled wrapper scopes" : "UNAVAILABLE: component sampling off",
                "sample_every_per_thread_component": stats.sample_every, "epoch": stats.epoch,
                "dropped_samples": stats.dropped, "boundary_dropped_samples": stats.boundary_dropped,
                "clock_errors": stats.clock_errors, "components": records,
                "scope": "One in64 entries per thread/component, deterministic not a whole-component cost estimate. Completed included scopes only; crossing epochs omitted and late completions may follow snapshot. Wall includes waits; caller CPU excludes other threads/compiler processes. Nested scopes overlap: do not sum or infer watts/core residency. Present scope includes host limiter; exact native API timings remain separate. Zero samples is not zero cost."]
    }
    private func archiveInspection() -> (tl_na_stats, tl_na_control, NativeArchivePresentation.Status) {
        var a = tl_na_stats(), control = tl_na_control()
        tl_vk_archive_inspect(&control, &a)
        let status = NativeArchivePresentation.status(mode: Int(control.mode), configuration: Int(control.configuration),
            apiAvailable: control.api_available != 0, snapshotValid: control.snapshot_valid != 0,
            supported: a.supported != 0, pending: a.pending, preparing: a.preparing != 0)
        return (a, control, status)
    }
    private func nativeArchiveReport() -> [String: Any] {
        let (a, control, status) = archiveInspection()
        var priority = tl_na_priority(); let priorityAvailable = tl_vk_archive_priority(&priority)
        let selection: [String: Any] = ["available": priorityAvailable, "eligible_slow_calls": priority.eligible,
            "higher_cost_replacements": priority.replaced, "lower_cost_or_preparing_rejections": priority.rejected,
            "known_requirement_satisfied_skips": priority.requirement_satisfied_skips,
            "highest_pending_host_ns": priority.highest_pending_ns, "lowest_pending_host_ns": priority.lowest_pending_ns,
            "scope": "Keep up to8 highest observed native-call durations, slowest first. Complete requests only; timing is not a semantic variant key. Skip extra preparation when opt-in verification already satisfied the archive requirement. No first-ever-hitch or net-energy guarantee."]
        var domainBuffer = a.last_verification_error_domain
        let errorDomain = withUnsafePointer(to: &domainBuffer) { p in
            p.withMemoryRebound(to: CChar.self, capacity: 64) { String(cString: $0) }
        }
        return ["plan_ids": ["M2", "M5", "M3"], "requested": a.requested != 0,
            "host_control": ["launch_mode": control.mode, "configuration_state": control.configuration,
                "driver_api_available": control.api_available != 0, "snapshot_valid": control.snapshot_valid != 0,
                "vulkan_device_observed": control.device_observed != 0, "status_code": status.code,
                "status_message": status.message],
            "last_user_inspection": lastArchiveInspection.map { $0 as Any } ?? NSNull(),
            "supported": a.supported != 0, "preparing": a.preparing != 0, "pending": a.pending,
            "verification_requested": a.verification_requested != 0, "verification_attempts": a.verification_attempts,
            "metal_archive_requirement_satisfied_calls": a.archive_requirement_satisfied, "verification_failed_calls": a.verification_failures,
            "last_verification_error_domain": errorDomain, "last_verification_error_code": a.last_verification_error_code,
            "verification_scope": "Opt-in extra FailOnBinaryArchiveMiss API attempt. Success is native Metal archive-requirement evidence, not a Vulkan cache hit or zero-cost compilation. Failure is not a proven miss; ordinary native fallback preserved. Verification adds overhead and stays OFF for energy comparisons.",
            "selection_policy": selection, "captured": a.descriptors_captured, "dropped": a.descriptors_dropped,
            "archive_attachments": a.archive_attachments, "archive_fallbacks": a.archive_fallbacks,
            "prepare_calls": a.prepare_calls, "prepared": a.prepared, "prepare_failures": a.prepare_failures,
            "restored_bytes": a.restored_bytes, "saved_bytes": a.saved_bytes,
            "read_failures": a.read_failures, "write_failures": a.write_failures, "prepare_ns": a.prepare_ns, "evicted_files": a.evicted_files, "evicted_bytes": a.evicted_bytes,
            "status": a.supported != 0 ? "MEASURED native archive mechanism counters" : "UNAVAILABLE: disabled, unavailable driver, or first native-pipeline support probe pending",
            "scope": "Since native driver configuration; up to8 retained slow native requests. Complete native descriptor copies, not Vulkan replay. Attachments/bytes are not verified hits. Preparation CPU/energy is additional; include its receipt. Library/front-end compilation can remain.",
            "energy_benefit": "UNVERIFIED"]
    }
    func inspectNativeArchive() {
        let (a, control, status) = archiveInspection()
        recordArchiveInspection(action: "inspect", stats: a, control: control, status: status)
    }
    private func recordArchiveInspection(action: String, stats: tl_na_stats, control: tl_na_control,
                                         status: NativeArchivePresentation.Status) {
        archiveInspectionSequence += 1
        let utc = ISO8601DateFormatter().string(from: Date())
        archiveMessage = NativeArchivePresentation.acknowledgement(sequence: archiveInspectionSequence, utc: utc,
            status: status, pending: control.snapshot_valid != 0 ? stats.pending : nil,
            restored: control.snapshot_valid != 0 ? stats.restored_bytes : nil)
        lastArchiveInspection = ["schema_version": 1, "plan_ids": ["M1", "M2", "M5"], "subsystem": "native_pipeline_archive",
            "action": action, "sequence": archiveInspectionSequence, "utc": utc, "observed_monotonic_seconds": now,
            "status_code": status.code, "status_message": status.message, "launch_mode": control.mode,
            "configuration_state": control.configuration, "driver_api_available": control.api_available != 0,
            "snapshot_valid": control.snapshot_valid != 0, "vulkan_device_observed": control.device_observed != 0,
            "native_support_confirmed": stats.supported != 0,
            "pending": control.snapshot_valid != 0 ? stats.pending as Any : NSNull(),
            "captured": control.snapshot_valid != 0 ? stats.descriptors_captured as Any : NSNull(),
            "restored_bytes": control.snapshot_valid != 0 ? stats.restored_bytes as Any : NSNull(), "preparing": stats.preparing != 0,
            "phase": running ? phase : "outside_test", "game_view_attached": gameVisible,
            "application_active": UIApplication.shared.applicationState == .active,
            "scope": "Read-only inspection/action status; no capture activation, preparation, cache-hit or energy claim"]
        if running { event("runtime", "[M2/M5 native-archive] \(action) inspection \(archiveInspectionSequence), status \(status.code), pending \(stats.pending)") }
    }
    func exportNativeArchiveInspection() {
        archiveInspectionFiles = []
        if lastArchiveInspection == nil { inspectNativeArchive() }
        guard let inspection = lastArchiveInspection else { return }
        do {
            let receipt: [String: Any] = ["schema_version": 1, "type": "native_archive_inspection",
                "exported_utc": ISO8601DateFormatter().string(from: Date()),
                "build_sha": Bundle.main.object(forInfoDictionaryKey: "HuskBuildCommit") as? String ?? "UNAVAILABLE",
                "configuration": attached, "inspection": inspection,
                "device_capabilities": EfficiencyDeviceInventory.snapshot(), "os": UIDevice.current.systemVersion,
                "driver_build": spatialReport()["driver_build"] ?? "UNAVAILABLE"]
            let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("PipelineInspection")
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            let file = dir.appendingPathComponent(UUID().uuidString + ".json")
            try EfficiencyMath.json(receipt).write(to: file, options: .atomic)
            archiveInspectionFiles = [file]
        } catch { archiveMessage = "Inspection export failed: \(error.localizedDescription). Existing test exports are unchanged." }
    }
    func prepareNativeArchive() {
        let (a, control, _) = archiveInspection()
        if let reason = NativeArchivePresentation.preparationBlocker(running: running, exporting: exporting,
            preparing: nativePreparing, gameVisible: gameVisible, active: UIApplication.shared.applicationState == .active) {
            recordArchiveInspection(action: "prepare_blocked", stats: a, control: control,
                status: .init(code: "prepare_blocked", message: reason)); return
        }
        guard tl_vk_archive_begin_prepare() else {
            let (fresh, freshControl, freshStatus) = archiveInspection()
            recordArchiveInspection(action: "prepare_not_started", stats: fresh, control: freshControl,
                status: .init(code: "prepare_not_started_" + freshStatus.code,
                    message: "Preparation did not start. " + (freshStatus.code == "ready" ? "Capture changed or another preparation reserved it. Inspect again; no compilation was started by this request." : freshStatus.message)))
            return
        }
        recordArchiveInspection(action: "prepare_started", stats: a, control: control,
            status: .init(code: "prepare_started", message: "Preparation reserved; the game will pause while captured requests are prepared."))
        nativePreparing = true; archiveMessage = "Game paused while captured native pipelines are prepared. One compiler call cannot be interrupted."
        let started = now, before = nativeArchiveReport()
        let preparationIdentity = metadata.filter { ["session_id", "build_sha", "device_identifier", "os"].contains($0.key) }
        let preparationConfiguration = attached
        let preparationDriver = spatialReport()["driver_build"] ?? "UNAVAILABLE"
        var cpu = tl_em_process(); tl_em_process_sample(false, &cpu); let cpuBefore = cpu.cpu_seconds
        husk_unity_set_paused(true)
        DispatchQueue.global(qos: .utility).async {
            let result = tl_vk_archive_prepare()
            DispatchQueue.main.async {
                let elapsed = self.now - started
                var afterCPU = tl_em_process(); tl_em_process_sample(false, &afterCPU)
                let deltaCPU: Double? = cpuBefore >= 0 && afterCPU.cpu_seconds >= cpuBefore ? afterCPU.cpu_seconds - cpuBefore : nil
                let receipt: [String: Any] = ["schema_version": 1, "type": "paused_native_pipeline_preparation", "game_pause_requested": true, "no_gpu_idle_wait": true,
                    "plan_ids": ["M2", "M5", "M3"], "build_sha": Bundle.main.object(forInfoDictionaryKey: "HuskBuildCommit") as? String ?? "UNAVAILABLE",
                    "utc": ISO8601DateFormatter().string(from: Date()), "configuration": preparationConfiguration,
                    "preceding_session_metadata": preparationIdentity, "driver_build": preparationDriver,
                    "started_monotonic_seconds": started, "ended_monotonic_seconds": started + elapsed,
                    "result": result, "measured_host_wall_seconds": elapsed,
                    "estimated_process_cpu_seconds": deltaCPU.map { $0 as Any } ?? NSNull(),
                    "before": before, "after": self.nativeArchiveReport(),
                    "scope": "Explicit extra preparation, game paused. Process CPU includes host and excludes compiler/system processes; wall includes callback scheduling. Pause requested, not a GPU-idle measurement. No measured watts/temperature/hits or energy saving. Include receipt in total-session comparisons."]
                do {
                    let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("PipelinePreparation")
                    try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
                    let file = dir.appendingPathComponent(UUID().uuidString + ".json")
                    try EfficiencyMath.json(receipt).write(to: file, options: .atomic); self.archiveFiles = [file]
                    self.archiveMessage = "Preparation result \(result). Receipt saved in Files > Husk > PipelinePreparation. Return to gameplay or share the receipt; benefit unverified."
                } catch { self.archiveMessage = "Preparation result \(result); receipt export failed: \(error.localizedDescription)" }
                self.nativePreparing = false
                if self.gameVisible && UIApplication.shared.applicationState == .active { husk_unity_set_paused(false) }
            }
        }
    }
    private func syncReport() -> [String: Any] {
        var s = tl_em_sync_stats(); tl_em_sync_snapshot(&s); var counts = s.counts
        let values = withUnsafeBytes(of: &counts) { Array($0.bindMemory(to: UInt64.self)) }
        let names = ["once_initializers", "once_contended_calls", "futex_waits", "futex_wake_calls", "futex_timeouts", "futex_spurious_host_wakes"]
        var report: [String: Any] = ["requested": s.requested, "status": s.requested ? "MEASURED included slow-path entries/events" : "UNAVAILABLE: CPU diagnostics disabled", "plan_ids": ["M8", "M3"], "subsystem": "compatibility_sync",
            "scope": "Included slow-path entries/events when observed; crossing-exclusion calls may appear separately. Completed once fast path deliberately uncounted; counts are not time, wasted work or energy"]
        for (name, value) in zip(names, values) { report[name] = value }
        return report
    }
    private func presentationClockReport() -> [String: Any] {
        var s = tl_pt_stats(); tl_pt_snapshot(&s)
        var records = Array(repeating: tl_pt_record(), count: 256)
        let count = records.withUnsafeMutableBufferPointer { tl_pt_records($0.baseAddress, UInt32($0.count)) }
        let rows: [[String: Any]] = records.prefix(Int(count)).map { v in
            ["sequence": v.sequence, "present_id": v.id, "raw_native_actual_ns": v.raw_actual,
             "estimated_guest_actual_ns": v.guest_actual, "estimated_guest_desired_ns": v.desired,
             "estimated_guest_earliest_ns": v.earliest, "margin_duration_ns": v.margin,
             "observed_guest_ns": v.observed_guest_ns, "observed_media_ns": v.observed_media_ns,
             "clock_read_uncertainty_ns": v.uncertainty_ns, "phase": "unknown history occurrence; may precede observation"]
        }
        return ["requested": s.requested, "feedback_only_requested": s.feedback_only, "plan_ids": ["M4", "M6", "M3"], "subsystem": "presentation_clock",
            "present_calls_observed": s.presents, "nonzero_timing_requests": s.timing_requests, "mapped_requests": s.mapped,
            "expired_requests": s.expired, "far_future_requests": s.far_future, "invalid_clock_or_overflow": s.invalid_clock,
            "unsupported_chains": s.unsupported, "guest_feedback_data_calls": s.feedback_calls, "feedback_records": s.feedback_records,
            "record_overwrites": s.record_overwrites, "record_contention": s.record_contention,
            "latest_clock_offset_ns": s.latest_offset_ns, "latest_read_uncertainty_ns": s.latest_uncertainty_ns,
            "feedback_last256": rows, "status": count > 0 ? "MEASURED native feedback; ESTIMATED cross-clock values" : "UNAVAILABLE: no captured guest-retrieved presentation feedback",
            "scope": "Passive guest data/deferred queries only; count-only calls uncounted; no history stolen. Session counters include excluded/lifecycle context and concurrent boundary reads. Driver may estimate earliest/actual time; not complete displayed-frame or energy accounting"]
    }
    private func submitCPUReport() -> [String: Any] {
        var s = tl_em_work_stats(); tl_em_work_snapshot(&s)
        return ["requested": cpuThreadSampling, "status": s.calls > 0 ? "MEASURED: caller-thread CPU during Vulkan submission" : "UNAVAILABLE: disabled/no valid calls",
                "calls": s.calls, "thread_cpu_ns": s.cpu_ns, "wall_ns": s.wall_ns, "dropped_records": s.dropped,
                "scope": "Sampled included submit calls; wall can wait/overlap, caller CPU excludes async encoding on other threads; no GPU time or power", "plan_ids": ["M3", "M6", "M8"]]
    }
    private func pipelineFeedbackReport() -> [String: Any] {
        var s = tl_pf_stats(); tl_pf_snapshot(&s)
        return ["requested": s.requested, "active": s.active, "enabled_devices": s.enabled_devices,
                "appended_extension_devices": s.appended_devices, "guest_enabled_devices": s.guest_enabled_devices,
                "unsupported_devices": s.unsupported_devices, "declined_devices": s.declined_devices,
                "injected_pipeline_infos": s.injected_pipelines, "passive_pipeline_infos": s.passive_pipelines,
                "skipped_batches": s.skipped_batches, "plan_ids": ["M2", "CACHE-01"],
                "scope": "Optional supported driver feedback; stage shader-library hits differ from whole-pipeline hits; neither guarantees no Metal pipeline work",
                "benefit_validation": "unverified"]
    }
    private func pipelineGroups() -> [[String: Any]] {
        var groups = Array(repeating: tl_pi_group(), count: 2048)
        let count = groups.withUnsafeMutableBufferPointer { tl_pi_copy_groups($0.baseAddress, UInt32($0.count)) }
        return groups.prefix(Int(count)).map { g in
            var hashes = g.shader_hashes, bits = g.stage_bits
            let hashList = withUnsafeBytes(of: &hashes) { Array($0.bindMemory(to: UInt64.self)) }
            let bitList = withUnsafeBytes(of: &bits) { Array($0.bindMemory(to: UInt32.self)) }
            let stages: [[String: Any]] = (0..<min(Int(g.shader_stages), 4)).map { i in
                ["stage_index": i, "vulkan_stage": bitList[i], "module_content_hash": String(format: "%016llx", hashList[i]), "module_known": hashList[i] != 0]
            }
            return ["signature_version": "core-v4", "full_core_fields_known": g.full_core != 0, "state_coverage_mask": g.coverage, "full_core_batch_calls": g.full_core_calls, "partial_signature": String(format: "%016llx", g.signature), "batch_calls": g.calls,
             "slow_batch_calls": g.slow_calls, "aggregate_host_ns": g.total_ns, "worst_host_ns": g.worst_ns,
             "first_pipeline_valid_feedback_calls": g.valid_feedback, "first_pipeline_application_hit_calls": g.application_hits,
             "first_pipeline_shader_stages": stages,
             "first_pipeline_last_stage_valid_mask": g.last_stage_valid_mask, "first_pipeline_last_stage_hit_mask": g.last_stage_hit_mask,
             "first_pipeline_valid_stage_feedback_count": g.stage_feedback_valid,
             "first_pipeline_stage_application_cache_hit_count": g.stage_application_hits,
             "scope": "Since launch; first sampled group per batch. Coverage bits shader1/fixed2/layout4/render8/base16; unsupported65536/missing131072. Recognised core fields only, not minimal compatibility/replay/cache keys; unhandled extensions remain partial.",
             "plan_ids": ["M2", "PIPE-01"]]
        }.sorted { ($0["worst_host_ns"] as? UInt64 ?? 0) > ($1["worst_host_ns"] as? UInt64 ?? 0) }
    }
    func stop() {
        guard running else { return }
        sample(forceBattery: true)
        var mediaBefore = 0.0, mediaAfter = 0.0
        tl_gput_native_exclude(true, &mediaBefore, &mediaAfter)
        metadata["gpu_clock_alignment_end"] = gpuClockAlignment()
        tl_cp_stop(); tl_em_stop(); tl_pt_monitor(false); tl_gput_end(); collectGPU(); drainEvents(); collectWindow()
        if let start = excludedAt { append(exclusionRow(start, now, mediaBefore, mediaAfter), to: &exclusions, limit: 2048) }
        timer?.invalidate(); timer = nil
        observers.forEach { NotificationCenter.default.removeObserver($0) }; observers = []
        UIDevice.current.isBatteryMonitoringEnabled = previousBatteryMonitoring
        var total = tl_em_stats(); tl_em_snapshot(true, &total)
        stoppedReport = ["schema_version": 13, "metadata": metadata, "duration_seconds": now - origin,
                         "summary": stats(total), "native_display_sampling": nativeDisplayReport(), "delayed_os_reports": EfficiencyMetricKit.shared.summary, "component_sampling": componentReport(), "driver_phases": driverPhaseReport(), "native_pipeline_archive": nativeArchiveReport(), "spatial_upscaling": spatialReport(), "pipeline_feedback_request": pipelineFeedbackReport(), "render_inventory": renderInventory(), "worker_policy": workerReport(), "pipeline_groups_since_launch": pipelineGroups(), "gpu_sampling": gpuReport(), "gpu_records": gpuRows, "gpu_windows": gpuWindowReport(), "submit_cpu_work": submitCPUReport(), "swapchain_budget": swapchainBudgetReport(), "queue_execution_options": queueExecutionReport(), "initialization_waits": initializationWaitReport(), "compatibility_sync": syncReport(), "presentation_clock": presentationClockReport(), "samples": samples, "windows": windows, "events": events, "exclusions": exclusions,
                         "battery_drain_pp_per_hour_estimated": battery.rate.map { $0 as Any } ?? NSNull(),
                         "battery_estimate_status": battery.status,
                         "battery_arithmetic_rate_pp_per_hour": battery.arithmeticRate.map { $0 as Any } ?? NSNull(),
                         "battery_decrease_steps": battery.decreases,
                         "battery_rate_display_policy": "Conservative: >=900 included battery-observation seconds and >=2 decreasing API transitions; still coarse, not electrical power",
                         "battery_included_sample_count": battery.sampleCount,
                         "battery_observed_drain_percentage_points": battery.drain,
                         "battery_first_included_fraction": battery.firstLevel.map { $0 as Any } ?? NSNull(),
                         "battery_last_included_fraction": battery.lastLevel.map { $0 as Any } ?? NSNull(),
                         "battery_estimate_observed_seconds": battery.seconds, "dropped_export_records": dropped,
                         "metric_plan_ids": ["frames": ["M1", "M4"], "pipeline_creation": ["M2"],
                                             "cpu_memory": ["M3"], "gpu_sampling": ["M3"], "guest_yields": ["M8"],
                                             "battery_thermal": ["M1", "M3", "M7"], "metal_capabilities": ["M3", "M9"]],
                         "metric_labels": ["host_cadence_cpu_memory_battery_thermal": "MEASURED (process/API scope)",
                                           "histogram_percentiles_battery_drain": "ESTIMATED",
                                           "sampled_command_buffer_gpu_intervals": "MEASURED only when gpu_sampling.status reports valid records",
                                           "per_frame_gpu_displayed_frames_aggregate_cache_hit_rate": "UNAVAILABLE",
                                           "process_peak_footprint": "MEASURED when returned Mach revision supports it; process lifetime, not session-only; otherwise UNAVAILABLE",
                                           "electrical_power_chip_temperature_surface_temperature": "EXTERNAL"],
                         "limitations": ["0.1 ms upper-bin nearest-rank percentiles; >=1 s overflow uses exact worst as conservative bound",
                                          "Host API stages: acquire, submit, present, sleep, graphics creation, compute creation; durations overlap",
                                          "Vulkan host cadence is not displayed-frame timing; no frame source for non-Vulkan games",
                                          "No measured watts, per-frame GPU attribution, degrees Celsius or energy saving",
                                          "Optional GPU intervals have partial queue/buffer/sample coverage; do not infer whole-device utilisation",
                                          "CPU includes host/LiveContainer work; 100% = one logical CPU",
                                          "Driver phase counters remain in attempt log if separately enabled",
                                          "Cache feedback may be unavailable; partial pipeline signatures are not cache keys",
                                          "Frame ring is separate from host/event recording; lost intervals and record categories are disclosed",
                                          "Monitoring overhead and physical-device correctness remain unverified"]]
        tl_vk_display_monitor(false)
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
                let triage = EfficiencyComponentTriage.build(report)
                var enriched = report; enriched["component_triage"] = triage
                try EfficiencyMath.json(enriched).write(to: json, options: .atomic)
                let summary = report["summary"] as? [String: Any] ?? [:], meta = report["metadata"] as? [String: Any] ?? [:]
                let rows = report["samples"] as? [[String: Any]] ?? []
                let cpu = rows.compactMap { $0["process_cpu_percent_one_core"] as? Double }
                let footprints = rows.compactMap { $0["footprint_bytes"] as? Int64 }
                let lifetimePeaks = rows.compactMap { $0["process_lifetime_peak_footprint_bytes"] as? Int64 }
                let thermal = Set(rows.compactMap { ($0["environment"] as? [String: Any])?["thermal_classification"] as? Int }).sorted()
                let feedback = report["pipeline_feedback_request"] as? [String: Any] ?? [:]
                let inventory = report["render_inventory"] as? [String: Any] ?? [:]
                let spatial = report["spatial_upscaling"] as? [String: Any] ?? [:]
                let textures = spatial["texture_observations"] as? [String: Any] ?? [:]
                let worker = report["worker_policy"] as? [String: Any] ?? [:]
                let presentation = report["presentation_clock"] as? [String: Any] ?? [:]
                let display = report["native_display_sampling"] as? [String: Any] ?? [:]
                let sync = report["compatibility_sync"] as? [String: Any] ?? [:]
                let submitWork = report["submit_cpu_work"] as? [String: Any] ?? [:]
                let gpu = report["gpu_sampling"] as? [String: Any] ?? [:]
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
                M4/M6 native display observer requested/available: \(display["requested"] ?? false) / \(display["available"] ?? false)
                Drawable-reported/driver-estimated events: \(display["direct_drawable_events"] ?? 0) / \(display["estimated_events"] ?? 0)
                Direct callback interval p95/p99: \(display["p95_ms_estimated"] ?? "UNAVAILABLE") / \(display["p99_ms_estimated"] ?? "UNAVAILABLE") ms (partial coverage; not full displayed FPS)
                Process CPU maximum sampled activity: \(cpu.max().map { String(format: "%.2f%%", $0) } ?? "UNAVAILABLE") (100% = one logical CPU, not whole-device usage)
                Maximum observed footprint: \(footprints.max().map { String(format: "%.3f GiB", Double($0) / 1073741824) } ?? "UNAVAILABLE") (not actual peak)
                Largest reported process lifetime footprint peak: \(lifetimePeaks.max().map { String(format: "%.3f GiB", Double($0) / 1073741824) } ?? "UNAVAILABLE") (host scope, including pre-session/excluded work)
                Thermal classifications observed: \(thermal)
                Battery status: \(report["battery_estimate_status"] ?? "UNAVAILABLE")
                Included battery samples/span: \(report["battery_included_sample_count"] ?? 0) / \(report["battery_estimate_observed_seconds"] ?? 0) seconds
                Observed battery decrease: \(report["battery_observed_drain_percentage_points"] ?? 0) percentage points
                ESTIMATED unplugged drain: \(report["battery_drain_pp_per_hour_estimated"] ?? "UNAVAILABLE") percentage points/hour (coarse).
                Dropped collector/export records: \(summary["dropped_collector_records"] ?? 0) / \(report["dropped_export_records"] ?? 0)

                Guest sched_yield observations (M8): \(summary["guest_yield_calls_cumulative"] ?? 0) calls; not proof of waste or energy use
                Frame distribution complete: \(summary["frame_distribution_complete"] ?? false)
                Dropped frame/host/event records: \(summary["dropped_frame_intervals_cumulative"] ?? 0) / \(summary["dropped_host_records_cumulative"] ?? 0) / \(summary["dropped_events_cumulative"] ?? 0)
                CPU/memory/battery/thermal samples, timestamped runtime events, phase markers and exclusions: diagnostics.json.
                M2 driver feedback request active/devices/injected: \(feedback["active"] ?? false) / \(feedback["enabled_devices"] ?? 0) / \(feedback["injected_pipeline_infos"] ?? 0)
                Stage cache feedback is separate from full pipeline reuse; no guaranteed compilation avoidance.
                M9 render inventory active/images/legacy areas: \(inventory["active"] ?? false) / \(inventory["observed_image_creations"] ?? 0) / \(inventory["observed_legacy_render_areas"] ?? 0)
                Inventory capacity/contention losses: \(inventory["dropped_capacity"] ?? 0) / \(inventory["dropped_contention"] ?? 0); hash probes \(inventory["hash_lookup_probes"] ?? 0)
                Render inventory is partial requested state; internal scene resolution remains unverified.
                M9 spatial configured: \(spatial["configured"] ?? false); input \(spatial["input_width"] ?? 0) × \(spatial["input_height"] ?? 0) -> output \(spatial["output_width"] ?? 0) × \(spatial["output_height"] ?? 0)
                M9 texture observation: \(textures["status"] ?? "UNAVAILABLE"); input \(textures["input_width"] ?? 0) × \(textures["input_height"] ?? 0) -> output \(textures["output_width"] ?? 0) × \(textures["output_height"] ?? 0)
                M9 spatial encode calls / failures: \(spatial["encoded_calls"] ?? 0) / \(spatial["failures"] ?? 0); successful calls do not prove visual/energy benefit.
                M7 worker policy requested/active: \(worker["requested_mode"] ?? 0) / \(worker["active_mode"] ?? 0)
                Adaptive requested / reason: \(worker["trial_requested"] ?? false) / \(worker["waiting_reason"] ?? "UNAVAILABLE")
                Admissions/rollbacks/caps/restores since launch: \(worker["admissions_since_launch"] ?? 0) / \(worker["rollback_requests_since_launch"] ?? 0) / \(worker["caps_applied_since_launch"] ?? 0) / \(worker["restores_applied_since_launch"] ?? 0)
                Core residency and scheduling energy benefit: UNAVAILABLE / unverified
                M3 sampled GPU timing: \(gpu["status"] ?? "UNAVAILABLE")
                GPU valid records / unresolved handlers: \(gpu["valid_records"] ?? 0) / \(gpu["unresolved_handlers_at_snapshot"] ?? 0)
                Observed sample-clipped GPU interval union: \(gpu["observed_interval_union_seconds"] ?? 0) seconds (partial coverage; not utilisation)
                GPU invalid/error/dropped/export losses: \(gpu["invalid_timestamps"] ?? 0) / \(gpu["command_buffer_errors"] ?? 0) / \(gpu["dropped_records_or_capture_attempts"] ?? 0) / \(gpu["dropped_export_records"] ?? 0)
                CPU thread snapshots: \(rows.filter { $0["cpu_threads"] != nil }.count); submit CPU/wall ns: \(submitWork["thread_cpu_ns"] ?? 0) / \(submitWork["wall_ns"] ?? 0); \(submitWork["status"] ?? "UNAVAILABLE")
                GPU aggregate windows/records/drops: \(gpu["aggregate_window_count"] ?? 0) / \(gpu["aggregate_records"] ?? 0) / \(gpu["dropped_aggregate_records"] ?? 0); raw cap losses remain explicit.
                M8 compatibility sync: \(sync)
                M4/M6 clock option/mapped/expired/future requests: \(presentation["requested"] ?? false) / \(presentation["mapped_requests"] ?? 0) / \(presentation["expired_requests"] ?? 0) / \(presentation["far_future_requests"] ?? 0)
                Presentation feedback: \(presentation["status"] ?? "UNAVAILABLE"); source may be estimated by driver, not complete display accounting.
                UNAVAILABLE: actual displayed frames, per-frame GPU attribution and aggregate cache-hit rate. Process peak footprint remains unavailable when the returned Mach revision does not supply a valid value. Per-request driver feedback is exported only where available.
                EXTERNAL: electrical power and numerical physical temperature. Thermal state is a classification.
                \(EfficiencyComponentTriage.text(triage))
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
    @State private var archiveSharing = false
    @State private var inspectionSharing = false
    var body: some View {
        NavigationView {
            Form {
                Section {
                    Text(monitor.message)
                    Toggle("Sample game GPU execution (Diagnostic)", isOn: $monitor.gpuSampling).disabled(monitor.running || monitor.exporting)
                    Text("Optional: samples completed game command buffers for 1 second every 10 seconds. Adds instrumentation; leave OFF for normal energy comparisons. No graphics change.")
                    Toggle("Sample CPU threads and submit work (Diagnostic)", isOn: $monitor.cpuThreadSampling).disabled(monitor.running || monitor.exporting)
                    Text("Optional thread CPU counters about every 10 seconds and caller CPU/wall time around submissions. Identifies CPU work, not core placement or watts. Adds overhead; OFF for clean energy comparisons.")
                    Toggle("Sample component CPU and waits (Diagnostic)", isOn: $monitor.componentSampling).disabled(monitor.running || monitor.exporting || monitor.nativePreparing)
                    Text("Samples Vulkan, JNI and synchronisation scopes. Adds diagnostic work; OFF for normal energy comparisons. Wall time includes waiting and nested scopes overlap.")
                    Toggle("Sample native display presentation (Diagnostic)", isOn: $monitor.displaySampling).disabled(monitor.running || monitor.exporting)
                    Text("Separates drawable-reported times from driver estimates. Requires the experimental driver (MetalFX or Native Cache Driver Only). Adds callback work; OFF for clean energy comparisons.")
                    Button("Start lightweight test") { monitor.start() }.disabled(monitor.running || monitor.exporting || monitor.nativePreparing)
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
                    Text(monitor.archiveMessage).textSelection(.enabled)
                    Text("Inspect refreshes status; it is not an enable switch. Enable capture in Game Graphics → Native Pipeline Cache → Archive Enabled, then fully restart Husk.")
                        .font(.caption)
                    Button("Inspect captured native pipelines") { monitor.inspectNativeArchive() }.disabled(monitor.nativePreparing)
                    Button("Share archive inspection") {
                        monitor.exportNativeArchiveInspection()
                        inspectionSharing = !monitor.archiveInspectionFiles.isEmpty
                    }.disabled(monitor.nativePreparing)
                    Button("Pause game and prepare captured pipelines") { monitor.prepareNativeArchive() }
                        .disabled(monitor.running || monitor.exporting || monitor.nativePreparing)
                    if monitor.running { Text("Stop and export the lightweight test before preparing pipelines.").font(.caption) }
                    else if monitor.exporting { Text("Wait for the export to finish before preparing pipelines.").font(.caption) }
                    Button("Share preparation receipt") { archiveSharing = true }.disabled(monitor.archiveFiles.isEmpty || monitor.nativePreparing)
                    Text("Archive mode must be enabled before launch. Only up to eight observed slow native requests are prepared. This costs CPU/time while the game pauses and cannot remove the same first-ever hitch. No power saving is assumed.")
                } header: { Text("Native Pipeline Preparation · Experimental") }
                Section {
                    Text("Return to gameplay after starting. This panel, background time and detached game views are excluded. Mark other interruptions explicitly. Tests remain in memory until stopped/exported; export before closing Husk.")
                    Text("Lightweight monitoring changes no graphics settings. Detailed Driver Profiling remains a separate option requiring restart; leave it off for energy comparisons.")
                    Text("CPU is process-scoped. Thermal state is not temperature. Sampled GPU timing is optional and may be unavailable. Electrical power requires external instrumentation. Monitoring overhead has not yet been measured on device.")
                }
            }
            .navigationTitle("Efficiency Test")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() }.disabled(monitor.nativePreparing) } }
        }
        .interactiveDismissDisabled(monitor.nativePreparing)
        .onAppear { monitor.panel(true); monitor.inspectNativeArchive() }.onDisappear { monitor.panel(false) }
        .sheet(isPresented: $sharing) { EfficiencyShare(items: monitor.files) }
        .sheet(isPresented: $archiveSharing) { EfficiencyShare(items: monitor.archiveFiles) }
        .sheet(isPresented: $inspectionSharing) { EfficiencyShare(items: monitor.archiveInspectionFiles) }
    }
}
private struct EfficiencyShare: UIViewControllerRepresentable {
    let items: [URL]
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: items, applicationActivities: nil) }
    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
