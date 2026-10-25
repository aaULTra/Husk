// SPDX-License-Identifier: GPL-2.0-or-later
import SwiftUI
import UIKit

/// What a person can change about how one game runs here, kept in the game's own folder (`settings.json`) so it goes when the game
/// does. Like LiveContainer's per-app settings: each game has its own, and nothing here touches another game.
struct TLAppSettings: Codable, Equatable {
    /// Which way up the screen is while the game runs.
    enum Orientation: String, Codable, CaseIterable, Identifiable {
        /// What the game asks for (its manifest), landscape when it does not say.
        case auto, landscape, portrait
        var id: String { rawValue }
        var title: String {
            switch self {
            case .auto: return "Automatic"
            case .landscape: return "Landscape"
            case .portrait: return "Portrait"
            }
        }
    }

    /// How many pixels the game draws for each point of the screen. Fewer pixels run faster and take less memory.
    enum Resolution: String, Codable, CaseIterable, Identifiable {
        case low, medium, high, native
        var id: String { rawValue }
        var title: String {
            switch self {
            case .low: return "Low"
            case .medium: return "Medium"
            case .high: return "High"
            case .native: return "Native"
            }
        }
        var detail: String {
            switch self {
            case .low: return "1 pixel per point. Fastest."
            case .medium: return "1.5 pixels per point."
            case .high: return "2 pixels per point. The default."
            case .native: return "Every pixel the screen has. Sharpest, and heaviest."
            }
        }
        @MainActor var scale: CGFloat {
            switch self {
            case .low: return 1
            case .medium: return 1.5
            case .high: return 2
            case .native: return UIScreen.main.scale
            }
        }
    }

    /// When the on-screen controller is offered.
    enum PadMode: String, Codable, CaseIterable, Identifiable {
        /// For the games that cannot be played without a controller (Unreal, PC games through DXVK), when none is connected.
        case auto, always, never
        var id: String { rawValue }
        var title: String {
            switch self {
            case .auto: return "Automatic"
            case .always: return "Always"
            case .never: return "Never"
            }
        }
    }

    /// Where the app opens: full screen, or a window over Husk that can be moved, resized and minimised (Multitasking).
    enum WindowMode: String, Codable, CaseIterable, Identifiable {
        /// As Settings › Multitasking says for every app.
        case auto, window, fullScreen
        var id: String { rawValue }
        var title: String {
            switch self {
            case .auto: return "Default"
            case .window: return "Window"
            case .fullScreen: return "Full Screen"
            }
        }
    }

    enum UnrealGraphics: String, Codable, CaseIterable, Identifiable {
        case automatic, gameDefault, sharpHigh, efficientHigh
        var id: String { rawValue }
        var title: String {
            switch self {
            case .automatic: return "Automatic"
            case .gameDefault: return "Game Default"
            case .sharpHigh: return "Sharp / High Quality"
            case .efficientHigh: return "Sharp / Efficient"
            }
        }
    }

    var unrealGraphics: UnrealGraphics = .automatic

    func usesSharpGraphics(for app: TLApp) -> Bool {
        guard app.report?.nativeEngine == .ue4 else { return false }
        switch unrealGraphics {
        case .gameDefault: return false
        case .sharpHigh, .efficientHigh: return true
        case .automatic:
            let name = app.label.lowercased()
            return (name.contains("minecraft") && name.contains("dungeons"))
                || (app.packageName?.lowercased().contains("dungeons") ?? false)
        }
    }

    enum WorkerScheduling: Int, Codable, CaseIterable, Identifiable {
        case gameDefault = 0, observe = 1, balanced = 2, adaptive = 3
        var id: Int { rawValue }
        var title: String {
            switch self {
            case .gameDefault: return "Game Default"
            case .observe: return "Observe Only"
            case .balanced: return "Balanced (Experimental)"
            case .adaptive: return "Adaptive Trial (Experimental)"
            }
        }
    }
    enum VulkanSubmission: Int, Codable, CaseIterable, Identifiable {
        case driverDefault = 0, asynchronous = 1
        var id: Int { rawValue }
        var title: String { self == .driverDefault ? "Driver Default" : "Async (Experimental)" }
    }
    var vulkanSubmission: VulkanSubmission = .driverDefault
    var engineOnlyLimiter = false
    var pipelineIdentification = false
    var pipelineFeedback = false
    var renderTargetInventory = false
    var driverPhaseProfiling = false
    var workerScheduling: WorkerScheduling = .balanced

    enum EfficientFrameRate: Int, Codable, CaseIterable, Identifiable {
        case cool = 30, smooth = 60
        var id: Int { rawValue }
        var title: String { self == .cool ? "30 FPS · Lower Power" : "60 FPS · Smoother" }
    }
    var efficientFrameRate: EfficientFrameRate = .smooth

    enum EfficientResolution: Int, Codable, CaseIterable, Identifiable {
        case custom = -1, automatic = 0, native = 100, ultra = 95, verySharp = 90, sharp = 85, quality = 80, balanced = 75, economical = 70, performance = 65
        var id: Int { rawValue }
        var title: String {
            switch self {
            case .custom: return "Custom · 1% Steps"
            case .automatic: return "Automatic · Reduced Resolution"
            case .native: return "Native · 100%"
            case .ultra: return "95% · Compare with Native"
            case .verySharp: return "90%"
            case .quality: return "80%"
            case .economical: return "70%"
            case .sharp: return "Sharp · 85%"
            case .balanced: return "Balanced · 75%"
            case .performance: return "Performance · 65%"
            }
        }
    }
    var efficientResolution: EfficientResolution = .automatic
    var customResolutionPercent = 80

    func usesEfficientGraphics(for app: TLApp) -> Bool {
        usesSharpGraphics(for: app) && (unrealGraphics == .automatic || unrealGraphics == .efficientHigh)
    }

    @MainActor func renderScale(for app: TLApp) -> CGFloat {
        guard usesSharpGraphics(for: app) else { return resolution.scale }
        let screen = UIScreen.main
        guard usesEfficientGraphics(for: app) else { return screen.scale }
        let fraction = tl_ue4_resolution_fraction(
            Int32((screen.bounds.width * screen.scale).rounded()),
            Int32((screen.bounds.height * screen.scale).rounded()),
            UIDevice.current.userInterfaceIdiom == .pad, Int32(efficientResolution == .custom ? customResolutionPercent : efficientResolution.rawValue))
        return screen.scale * CGFloat(fraction)
    }

    @MainActor func fullscreenResolutionEstimate(for app: TLApp) -> String {
        let size = UIScreen.main.bounds.size
        let scale = renderScale(for: app)
        let width = Int((max(size.width, size.height) * scale).rounded()) & ~7
        let height = Int((min(size.width, size.height) * scale).rounded()) & ~7
        return "\(width) × \(height)"
    }

    var orientation: Orientation = .auto
    var window: WindowMode = .auto
    var resolution: Resolution = .high
    /// The frames-per-second readout in the top bar.
    var showStats = true
    /// Start with nothing over the picture: no bar, no controller, no readout. Three fingers tapped together bring them back.
    var cleanView = false
    /// Stop the screen from dimming and locking while the game is on.
    var keepAwake = true
    var pad: PadMode = .auto
    /// Whether the controller is showing right now (the Pad button in the top bar toggles it).
    var padShown = true
    var padOpacity = 1.0
    var haptics = true
    /// Geometry Dash only: load Geode, its mod loader (Geode.swift).
    var geode = false

    init() {}

    // Settings written by an older Husk lack the keys a newer one added; each falls back to its default.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        customResolutionPercent = min(100, max(65, try c.decodeIfPresent(Int.self, forKey: .customResolutionPercent) ?? 80))
        efficientResolution = try c.decodeIfPresent(EfficientResolution.self, forKey: .efficientResolution) ?? .automatic
        vulkanSubmission = try c.decodeIfPresent(VulkanSubmission.self, forKey: .vulkanSubmission) ?? .driverDefault
        engineOnlyLimiter = try c.decodeIfPresent(Bool.self, forKey: .engineOnlyLimiter) ?? false
        pipelineIdentification = try c.decodeIfPresent(Bool.self, forKey: .pipelineIdentification) ?? false
        pipelineFeedback = try c.decodeIfPresent(Bool.self, forKey: .pipelineFeedback) ?? false
        renderTargetInventory = try c.decodeIfPresent(Bool.self, forKey: .renderTargetInventory) ?? false
        driverPhaseProfiling = try c.decodeIfPresent(Bool.self, forKey: .driverPhaseProfiling) ?? false
        workerScheduling = try c.decodeIfPresent(WorkerScheduling.self, forKey: .workerScheduling) ?? .balanced
        efficientFrameRate = try c.decodeIfPresent(EfficientFrameRate.self, forKey: .efficientFrameRate) ?? .smooth
        unrealGraphics = try c.decodeIfPresent(UnrealGraphics.self, forKey: .unrealGraphics) ?? .automatic
        orientation = try c.decodeIfPresent(Orientation.self, forKey: .orientation) ?? .auto
        resolution = try c.decodeIfPresent(Resolution.self, forKey: .resolution) ?? .high
        showStats = try c.decodeIfPresent(Bool.self, forKey: .showStats) ?? true
        cleanView = try c.decodeIfPresent(Bool.self, forKey: .cleanView) ?? false
        keepAwake = try c.decodeIfPresent(Bool.self, forKey: .keepAwake) ?? true
        pad = try c.decodeIfPresent(PadMode.self, forKey: .pad) ?? .auto
        padShown = try c.decodeIfPresent(Bool.self, forKey: .padShown) ?? true
        padOpacity = try c.decodeIfPresent(Double.self, forKey: .padOpacity) ?? 1.0
        haptics = try c.decodeIfPresent(Bool.self, forKey: .haptics) ?? true
        geode = try c.decodeIfPresent(Bool.self, forKey: .geode) ?? false
        window = try c.decodeIfPresent(WindowMode.self, forKey: .window) ?? .auto
    }

    private static func url(_ id: String) -> URL {
        TranslationLayer.root.appendingPathComponent(id, isDirectory: true).appendingPathComponent("settings.json")
    }

    static func load(_ id: String) -> TLAppSettings {
        (try? Data(contentsOf: url(id))).flatMap { try? JSONDecoder().decode(TLAppSettings.self, from: $0) } ?? TLAppSettings()
    }

    func save(_ id: String) {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        // The folder is gone when the app was removed while its settings page was open.
        guard FileManager.default.fileExists(atPath: Self.url(id).deletingLastPathComponent().path),
              let data = try? encoder.encode(self) else { return }
        try? data.write(to: Self.url(id), options: .atomic)
    }
}

// MARK: - The settings page

/// One game's settings, opened from its page or from its tile's menu.
struct TLAppSettingsView: View {
    let app: TLApp

    @State private var efficiencySheet = false
    @ObservedObject private var store = TranslationLayerStore.shared
    @ObservedObject private var geode = GeodeSupport.shared
    @State private var settings: TLAppSettings
    @State private var name: String
    @State private var dataSize: String = "…"
    @State private var confirmReset = false
    @FocusState private var nameFocused: Bool

    init(app: TLApp) {
        self.app = app
        _settings = State(initialValue: TLAppSettings.load(app.id))
        _name = State(initialValue: app.label)
    }

    /// The game is loaded in this run of Husk, so what it keeps cannot be swapped from under it.
    private var inUse: Bool {
        guard let loaded = husk_native_loaded_apk().map({ String(cString: $0) }), let apk = app.apks.first else { return false }
        return loaded == apk
    }

    private var dataDirs: [URL] {
        let dir = TranslationLayer.root.appendingPathComponent(app.id, isDirectory: true)
        return ["unity-data", "cocos-data", "minecraft-data", "sdl-data", "ue4-data", "gta-data", "na-data", "godot-data", "flutter-data", "gm-data", "web"]
            .map { dir.appendingPathComponent($0, isDirectory: true) }
            .filter { FileManager.default.fileExists(atPath: $0.path) }
    }

    var body: some View {
        Form {
            Section {
                HStack(spacing: 14) {
                    AppIcon(path: app.iconPath, size: 52)
                    TextField("Name", text: $name)
                        .focused($nameFocused)
                        .submitLabel(.done)
                        .onSubmit { rename() }
                        .font(.system(size: 18, weight: .semibold))
                }
                .padding(.vertical, 2)
            } footer: {
                Text("What the game is called in Husk. The game itself is not changed.")
            }

            Section {
                Picker("Orientation", selection: $settings.orientation) {
                    ForEach(TLAppSettings.Orientation.allCases) { Text($0.title).tag($0) }
                }
                if settings.usesSharpGraphics(for: app) {
                    LabeledContent("Resolution", value: "See Game Graphics")
                } else {
                    Picker("Resolution", selection: $settings.resolution) {
                        ForEach(TLAppSettings.Resolution.allCases) { Text($0.title).tag($0) }
                    }
                }
                Toggle("Performance readout", isOn: $settings.showStats)
                Toggle("Keep the screen on", isOn: $settings.keepAwake)
            } header: {
                Text("Display")
            } footer: {
                Text("\(settings.usesEfficientGraphics(for: app) ? "Use Game Graphics to choose the rendering resolution." : (settings.usesSharpGraphics(for: app) ? "The graphics preset uses Native resolution." : settings.resolution.detail)) Orientation and resolution apply the next time the game starts, and a game already "
                   + "running in this session needs Husk closed and opened again.")
            }

            if app.report?.nativeEngine == .ue4 {
                Section {
                    Picker("Graphics", selection: $settings.unrealGraphics) {
                        ForEach(TLAppSettings.UnrealGraphics.allCases) { Text($0.title).tag($0) }
                    }
                    Picker("Vulkan Submission", selection: $settings.vulkanSubmission) {
                        ForEach(TLAppSettings.VulkanSubmission.allCases) { Text($0.title).tag($0) }
                    }
                    Toggle("Engine-only 60 FPS Limiter (Diagnostic)", isOn: $settings.engineOnlyLimiter)
                    Text("Off keeps the existing engine + host limiter. On requests engine-only pacing at 60 FPS; verify actual cadence in a short test. Thermal fallback caps remain active. Fully restart after changes.").font(.caption)
                    Toggle("Pipeline Identification (Diagnostic)", isOn: $settings.pipelineIdentification)
                    Toggle("Pipeline Creation Feedback (Diagnostic)", isOn: $settings.pipelineFeedback).disabled(!settings.pipelineIdentification)
                    Text("Optional driver feedback request, only where advertised; requires identification and full restart. Adds diagnostic overhead, with no guaranteed cache hits or savings.").font(.caption)
                    Toggle("Render Target Inventory (Diagnostic)", isOn: $settings.renderTargetInventory)
                    Text("Records requested image and render-area sizes for MetalFX investigation; adds CPU observation overhead. No upscaling or resolution change. Restart after changing.").font(.caption)
                    Toggle("Driver Phase Profiling", isOn: $settings.driverPhaseProfiling)
                    Button("Performance & Efficiency Diagnostics") { efficiencySheet = true }
                        .sheet(isPresented: $efficiencySheet) { EfficiencyDiagnosticsView() }
                    Picker("Worker Scheduling", selection: $settings.workerScheduling) {
                        ForEach(TLAppSettings.WorkerScheduling.allCases) { Text($0.title).tag($0) }
                    }
                    LabeledContent("Active Preset", value: settings.usesEfficientGraphics(for: app) ? "Sharp / Efficient" : (settings.usesSharpGraphics(for: app) ? "Sharp / High Quality" : "Game Default"))
                    if settings.usesEfficientGraphics(for: app) {
                        Picker("Rendering Resolution", selection: $settings.efficientResolution) {
                            ForEach(TLAppSettings.EfficientResolution.allCases) { Text($0.title).tag($0) }
                        }
                        LabeledContent("Fullscreen Target", value: settings.fullscreenResolutionEstimate(for: app))
                        if settings.efficientResolution == .custom {
                            LabeledContent("Render Scale", value: "\(settings.customResolutionPercent)%")
                            Slider(value: Binding(get: { Double(settings.customResolutionPercent) }, set: { settings.customResolutionPercent = Int($0.rounded()) }), in: 65...100, step: 1)
                        }
                        Picker("Frame Limit", selection: $settings.efficientFrameRate) {
                            ForEach(TLAppSettings.EfficientFrameRate.allCases) { Text($0.title).tag($0) }
                        }
                    }
                } header: {
                    Text("Game Graphics")
                } footer: {
                    Text("Automatic uses Sharp / Efficient for Minecraft Dungeons: a display-based resolution budget, high texture detail, 8× filtering and lighter shadows/effects. "
                       + "Pipeline Identification is diagnostic and adds overhead; restart before testing and keep it off for ordinary energy comparisons. Async submission is experimental; keep Driver Default if it causes instability. Driver Phase Profiling is off by default and adds MoltenVK activity counters to the log for short diagnostic sessions; it adds overhead and does not measure pure GPU execution or power. Fully restart after enabling or disabling it. Compare resolution steps from Native downward at your usual viewing distance and keep the lowest that still looks equally sharp to you. "
                       + "The default target is 60 FPS; 30 FPS is an optional lower-power mode. "
                       + "Automatic deliberately uses reduced resolution, with a larger pixel budget on iPad than iPhone. Native · 100% requests the full display resolution. Fullscreen Target estimates the next landscape launch on this display; windowed sizes can differ, and changes require Husk to be fully restarted. This is a starting point, not a measured optimum or an FPS guarantee. Percentages scale both dimensions. Open a folding device to the desired display before restarting Husk; live folding is not supported. "
                       + "When iOS reports serious heat, the cap drops to 30 FPS, or 20 at critical heat, and recovers after cooling. "
                       + "Sharp / High Quality keeps the previous maximum-quality preset. Game Default removes the overrides. "
                       + "For Dungeons only, Balanced caps named normal workers at Default QoS and background workers at Utility. "
                       + "Other thread roles are preserved. Observe Only logs requested QoS without changing it. "
                       + "Adaptive Trial uses a CPU-capacity hint, preserves critical roles, and waits for healthy 60 FPS cadence with only inexpensive pipeline creation before requesting extra worker caps. Frame spikes or expensive pipeline calls request rollback. Changes apply on worker self checkpoints, not immediately to busy threads. It does not know individual job deadlines or measure energy savings. "
                       + "This does not pin CPU cores and may affect frame times. Close Husk completely and reopen after changes.")
                }
            }

            Section {
                Picker("Open In", selection: $settings.window) {
                    ForEach(TLAppSettings.WindowMode.allCases) { m in
                        Text(m == .auto ? "Default (\(AppWindows.defaultWindowed ? "Window" : "Full Screen"))" : m.title).tag(m)
                    }
                }
            } header: {
                Text("Multitasking")
            } footer: {
                Text("In a window, \(app.label) runs over Husk: move it by its title bar, resize it from the corner, and minimise it to "
                   + "the dock at the edge of the screen while you use the rest of Husk.")
            }

            Section {
                Toggle("Hide the interface", isOn: $settings.cleanView)
            } header: {
                Text("Screenshots")
            } footer: {
                Text("The game starts with nothing over it: no bar, no controller, no readout. Tap with three fingers at once to bring "
                   + "the bar back, and again to hide it. The Hide button in the bar does the same while playing.")
            }

            if app.packageName == GeodeSupport.gamePackage {
                Section {
                    Toggle("Geode", isOn: $settings.geode)
                    if settings.geode { geodeStatus }
                } header: {
                    Text("Mods")
                } footer: {
                    Text("Geode is the mod loader for Geometry Dash. With it on, Husk downloads Geode for this version of the "
                       + "game, and mods are found and installed in the game itself, from Geode's button on the main menu. "
                       + "Applies the next time the game starts.")
                }
            }

            Section {
                Picker("On-screen controller", selection: $settings.pad) {
                    ForEach(TLAppSettings.PadMode.allCases) { Text($0.title).tag($0) }
                }
                if settings.pad != .never {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Opacity")
                        Slider(value: $settings.padOpacity, in: 0.3...1)
                    }
                    Toggle("Vibrate on a press", isOn: $settings.haptics)
                }
            } header: {
                Text("Controller")
            } footer: {
                Text("Automatic offers the controller for games that cannot be played without one (Unreal Engine games), when no real "
                   + "controller is connected. Always offers it for any game that understands one. A paired controller is always used.")
            }

            Section {
                Button { AppClip.generate(for: app) } label: {
                    Label("Generate App Clip", systemImage: "apps.iphone.badge.plus")
                }
            } header: {
                Text("Home Screen")
            } footer: {
                Text("Puts \(app.label) on your Home Screen with its own icon. Tapping it opens Husk straight into the game. Husk "
                   + "downloads a profile: open Settings, tap Profile Downloaded, then Install.")
            }

            Section {
                DetailRow(label: "Saved by the game", value: dataSize, mono: false)
                Button(role: .destructive) { confirmReset = true } label: {
                    Label("Reset Game Data", systemImage: "arrow.counterclockwise")
                }
                .disabled(inUse || dataDirs.isEmpty)
            } header: {
                Text("Data")
            } footer: {
                Text(inUse ? "The game is loaded in this session. Close Husk completely and open it again to reset its data."
                           : "Deletes what the game saved and downloaded here: saves, settings and caches. The game itself stays.")
            }
        }
        .huskForm()
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
        .onChange(of: settings) { $0.save(app.id) }
        .onChange(of: settings.geode) { on in
            if on { Task { await geode.prepare(app) } } else { geode.remove(app) }
        }
        .onChange(of: nameFocused) { focused in if !focused { rename() } }
        .onDisappear { rename() }
        .task { dataSize = await Self.measure(dataDirs) }
        .confirmationDialog("Reset the data of \(app.label)?", isPresented: $confirmReset, titleVisibility: .visible) {
            Button("Reset Game Data", role: .destructive) {
                for dir in dataDirs { try? FileManager.default.removeItem(at: dir) }
                HuskLog.log("tl", "reset the data of \(app.label)")
                Task { dataSize = await Self.measure(dataDirs) }
            }
            Button("Cancel", role: .cancel) { }
        } message: {
            Text("Saves, settings and caches the game made here are deleted.")
        }
    }

    @ViewBuilder
    private var geodeStatus: some View {
        switch geode.current(app) {
        case .idle:
            Button("Download Geode") { Task { await geode.prepare(app) } }
        case .working(let what):
            HStack(spacing: 10) { ProgressView(); Text(what).foregroundStyle(.secondary) }
        case .ready(let version):
            LabeledContent("Geode", value: "v\(version), ready")
        case .failed(let why):
            VStack(alignment: .leading, spacing: 6) {
                Text(why).font(.footnote).foregroundStyle(.orange)
                Button("Try Again") { Task { await geode.prepare(app) } }
            }
        }
    }

    private func rename() {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, trimmed != app.label else { return }
        store.rename(app, to: trimmed)
    }

    private static func measure(_ dirs: [URL]) async -> String {
        await Task.detached(priority: .utility) {
            var bytes: Int64 = 0
            for dir in dirs {
                let walker = FileManager.default.enumerator(at: dir, includingPropertiesForKeys: [.fileSizeKey, .isRegularFileKey])
                while let url = walker?.nextObject() as? URL {
                    let values = try? url.resourceValues(forKeys: [.fileSizeKey, .isRegularFileKey])
                    if values?.isRegularFile == true { bytes += Int64(values?.fileSize ?? 0) }
                }
            }
            return bytes == 0 ? "nothing" : ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
        }.value
    }
}
