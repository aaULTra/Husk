// SPDX-License-Identifier: GPL-2.0-or-later
import SwiftUI
import UIKit
import Metal

@MainActor enum EfficiencyDeviceInventory {
    static func snapshot() -> [String: Any] {
        let device = EfficiencyHardware.identifier()
        var result: [String: Any] = ["plan_ids": ["M3", "M10"], "device_identifier": device,
            "os": UIDevice.current.systemVersion, "logical_processor_count": ProcessInfo.processInfo.processorCount,
            "active_logical_processor_count": ProcessInfo.processInfo.activeProcessorCount,
            "physical_memory_bytes": ProcessInfo.processInfo.physicalMemory,
            "display_maximum_refresh_capability_hz": UIScreen.main.maximumFramesPerSecond,
            "profile_status": ["iPad16,5", "iPad16,6"].contains(device) ? "Documented M4 reference controls; energy optimum UNVERIFIED" : "No verified device-specific efficiency defaults; manual controls retained",
            "electrical_power": "EXTERNAL", "numerical_temperature": "EXTERNAL",
            "scope": "Runtime API capabilities, not measured core placement, actual refresh, GPU utilisation or a validated power/thermal profile. Future Duo requires its own baseline."]
        if let metal = MTLCreateSystemDefaultDevice() {
            result["metal_device_name"] = metal.name
            result["metal_registry_id"] = metal.registryID
            result["metal_max_buffer_bytes"] = metal.maxBufferLength
        }
        return result
    }
}

struct EfficiencyProfilesView: View {
    @Binding var settings: TLAppSettings
    let game: String
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var monitor = EfficiencyDiagnostics.shared
    @State private var profiles: [EfficiencyProfile] = []
    @State private var name = "Experiment"
    @State private var message = "Local experimental profiles. Nothing is applied automatically. Restart after applying."
    @State private var previous: TLAppSettings?
    @State private var exported: [URL] = []
    @State private var sharing = false
    private var device: String { EfficiencyHardware.identifier() }
    private var store: EfficiencyProfileStore {
        EfficiencyProfileStore(directory: FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("EfficiencyProfiles").appendingPathComponent(device))
    }
    private var blocked: Bool { monitor.running || monitor.exporting || monitor.nativePreparing }
    private var selection: EfficiencyProfile.Controls {
        .init(graphics: settings.unrealGraphics.rawValue, orientation: settings.orientation.rawValue, window: settings.window.rawValue,
              resolution: settings.efficientResolution.rawValue, customPercent: settings.customResolutionPercent,
              fps: settings.efficientFrameRate.rawValue, worker: settings.workerScheduling.rawValue, submission: settings.vulkanSubmission.rawValue,
              spatial: settings.spatialUpscaling, spatialPercent: settings.spatialInputPercent, archive: settings.nativePipelineArchiveMode,
              archiveVerification: settings.nativeArchiveVerification, engineOnly: settings.engineOnlyLimiter,
              clockTimed: settings.clockPresentation, clockFeedback: settings.feedbackClockCorrection)
    }
    private func reload() { profiles = store.load(device: device, game: game) }
    private func save() {
        do {
            let profile = EfficiencyProfile(name: name, device: device, game: game,
                build: Bundle.main.object(forInfoDictionaryKey: "HuskBuildCommit") as? String ?? "UNAVAILABLE", controls: selection)
            _ = try store.save(profile, device: device); reload(); message = "Saved for this device/game only. Performance and energy remain unverified."
        } catch { message = "Profile not saved: \(error.localizedDescription). Check settings/name or the 16-profile limit." }
    }
    private func apply(_ profile: EfficiencyProfile) {
        do {
            let p = try profile.validated(for: device, game: game), c = p.controls
            previous = settings
            guard let graphics = TLAppSettings.UnrealGraphics(rawValue: c.graphics),
                  let orientation = TLAppSettings.Orientation(rawValue: c.orientation),
                  let window = TLAppSettings.WindowMode(rawValue: c.window),
                  let resolution = TLAppSettings.EfficientResolution(rawValue: c.resolution),
                  let fps = TLAppSettings.EfficientFrameRate(rawValue: c.fps),
                  let worker = TLAppSettings.WorkerScheduling(rawValue: c.worker),
                  let submission = TLAppSettings.VulkanSubmission(rawValue: c.submission) else { throw EfficiencyProfile.Failure.invalid }
            settings.unrealGraphics = graphics; settings.orientation = orientation; settings.window = window
            settings.efficientResolution = resolution; settings.customResolutionPercent = c.customPercent; settings.efficientFrameRate = fps
            settings.workerScheduling = worker; settings.vulkanSubmission = submission
            settings.spatialUpscaling = c.spatial; settings.spatialInputPercent = c.spatialPercent
            settings.nativePipelineArchiveMode = c.archive; settings.nativeArchiveVerification = c.archiveVerification
            settings.engineOnlyLimiter = c.engineOnly; settings.clockPresentation = c.clockTimed; settings.feedbackClockCorrection = c.clockFeedback
            settings.driverPhaseProfiling = false; settings.pipelineIdentification = false; settings.pipelineFeedback = false; settings.renderTargetInventory = false
            message = "Applied \(p.name): \(c.fps) FPS, resolution budget \(c.resolution), worker \(c.worker), submission \(c.submission). Fully restart. Launch diagnostics reset OFF; session sampling controls are separate. Benefit unverified."
        } catch { message = "Profile rejected: device, game, version or controls do not match." }
    }
    private func restoreReference() {
        previous = settings
        settings.unrealGraphics = .efficientHigh; settings.orientation = .landscape; settings.window = .fullScreen
        settings.efficientResolution = .automatic; settings.efficientFrameRate = .smooth
        settings.workerScheduling = .balanced; settings.vulkanSubmission = .driverDefault
        settings.spatialUpscaling = false; settings.nativePipelineArchiveMode = 0; settings.nativeArchiveVerification = false
        settings.engineOnlyLimiter = false; settings.clockPresentation = false; settings.feedbackClockCorrection = false
        settings.driverPhaseProfiling = false; settings.pipelineIdentification = false; settings.pipelineFeedback = false; settings.renderTargetInventory = false
        message = "Restored documented M4 reference controls. Fully restart and verify actual 2128×1600 presentation. This is not a verified energy optimum."
    }
    var body: some View {
        NavigationView {
            Form {
                Section {
                    Text(device).font(.headline)
                    Text(message)
                    TextField("Profile name", text: $name)
                    Button("Save current graphics controls") { save() }.disabled(blocked)
                    if ["iPad16,5", "iPad16,6"].contains(device) {
                        Button("Restore M4 reference controls") { restoreReference() }.disabled(blocked)
                    }
                    Button("Undo last profile change") { if let value = previous { settings = value; previous = nil; message = "Prior settings restored; fully restart." } }.disabled(previous == nil || blocked)
                } footer: {
                    Text("Profiles are manual, device/game-specific and unverified. Changing a profile can change resolution, quality, FPS and scheduling; inspect its controls. Up to 16 retained; no automatic defaults for unknown devices or Duo.")
                }
                Section("Saved local experiments") {
                    ForEach(profiles) { p in
                        VStack(alignment: .leading, spacing: 5) {
                            Text(p.name).font(.headline)
                            Text("\(p.controls.fps) FPS · budget \(p.controls.resolution) · spatial \(p.controls.spatial ? "ON" : "OFF") · worker \(p.controls.worker) · submit \(p.controls.submission)").font(.caption)
                            Button("Apply controls") { apply(p) }.disabled(blocked)
                            Button("Share profile") { do { exported = [try store.save(p, device: device)]; sharing = true } catch { message = error.localizedDescription } }.disabled(blocked)
                            Button("Delete local profile", role: .destructive) { do { try store.remove(p, device: device); reload() } catch { message = error.localizedDescription } }.disabled(blocked)
                        }
                    }
                }
            }
            .navigationTitle("Device Graphics Profiles")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
            .onAppear { reload() }
            .sheet(isPresented: $sharing) { EfficiencyAuxiliaryShare(items: exported) }
        }
    }
}

struct EfficiencyMetricKitView: View {
    @ObservedObject private var reports = EfficiencyMetricKit.shared
    @Environment(\.dismiss) private var dismiss
    @State private var sharing = false
    var body: some View {
        NavigationView {
            Form {
                Toggle("Collect delayed OS reports", isOn: Binding(get: { reports.enabled }, set: { reports.setEnabled($0) }))
                Text(reports.message)
                Text("MetricKit delivers periodic host-process metrics/diagnostics, often much later. Availability and LiveContainer attribution need validation. It does not provide instant Dungeons watts or a numerical thermometer. Reports stay local and are shared only when you choose.")
                Text("Retained reports: \(reports.files.count) /8; maximum 4 MiB each. Old owned OS reports are rotated; game logs and profiles are untouched.")
                Button("Refresh received reports") { reports.reload() }
                Button("Share retained OS reports") { sharing = true }.disabled(reports.files.isEmpty)
            }
            .navigationTitle("Delayed OS Reports")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
            .onAppear { reports.reload() }
            .sheet(isPresented: $sharing) { EfficiencyAuxiliaryShare(items: reports.files) }
        }
    }
}
private struct EfficiencyAuxiliaryShare: UIViewControllerRepresentable {
    let items: [URL]
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: items, applicationActivities: nil) }
    func updateUIViewController(_ view: UIActivityViewController, context: Context) {}
}
