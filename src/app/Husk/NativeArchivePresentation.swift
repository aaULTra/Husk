// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation

/// Presentation policy only. Unknown native support stays unknown; inspecting
/// never enables capture, prepares pipelines or changes graphics settings.
enum NativeArchivePresentation {
    struct Status {
        let code: String
        let message: String
    }
    static func acknowledgement(sequence: Int, utc: String, status: Status,
                                pending: UInt32?, restored: UInt64?) -> String {
        let counts = pending.flatMap { count in restored.map { "Pending: \(count); restored: \($0) bytes. Bytes are not cache-hit evidence." } }
        return "Inspection #\(sequence) · \(utc)\n\(status.message)\n\(counts ?? "Native counters: UNAVAILABLE; not an empty capture.")"
    }
    static func status(mode: Int, configuration: Int, apiAvailable: Bool,
                       snapshotValid: Bool, supported: Bool, pending: UInt32,
                       preparing: Bool) -> Status {
        if preparing { return Status(code: "preparing", message: "Preparation is already running. Wait for its receipt; one Metal compiler call cannot be interrupted.") }
        if mode == 0 { return Status(code: "off", message: "Capture was OFF when this game launched. Set Game Graphics → Native Pipeline Cache → Archive Enabled, then fully close and reopen Husk. MetalFX alone does not enable archive capture.") }
        if mode == 1 { return Status(code: "driver_only", message: "Driver Only is active; archive capture is OFF. Select Archive Enabled, then fully close and reopen Husk.") }
        switch configuration {
        case 0: return Status(code: "not_configured", message: "Archive mode was requested, but game archive configuration has not completed. Launch Dungeons with Sharp / Efficient. If already playing, export diagnostics; repeatedly pressing Inspect will not configure it.")
        case 2: return Status(code: "wrong_project", message: "Archive capture is restricted to the recognised Dungeons project. This launch was not recognised; export diagnostics.")
        case 3: return Status(code: "graphics_disabled", message: "Archive configuration requires the Sharp graphics path. Select Sharp / Efficient and fully restart Husk.")
        case 4: return Status(code: "driver_api_missing", message: "The loaded driver lacks the required archive functions. Export diagnostics and the build identity; no need to repeat gameplay.")
        case 5: return Status(code: "configuration_rejected", message: "The driver rejected archive configuration. Export diagnostics; no preparation was started.")
        case 6: return Status(code: "device_ended", message: "The Vulkan device used for archive capture has ended. Export existing results before restarting Husk.")
        case 1: break
        default: return Status(code: "unknown_configuration", message: "Archive configuration is unknown. Export diagnostics; no preparation was started.")
        }
        guard apiAvailable else { return Status(code: "driver_api_missing", message: "Required archive functions are unavailable. Export diagnostics; no preparation was started.") }
        guard snapshotValid else { return Status(code: "snapshot_unavailable", message: "The driver did not return a valid archive snapshot. Export diagnostics; unavailable data is not an empty capture.") }
        guard supported else { return Status(code: "support_unconfirmed", message: "Archive configuration was accepted, but native archive support is not confirmed. This can mean the first native pipeline probe is pending or failed. If gameplay has started, export diagnostics; do not keep playing to force a capture.") }
        if pending == 0 { return Status(code: "empty", message: "Inspection succeeded: 0 pipelines pending. Capture is active, but no slow native request is waiting for preparation. Export diagnostics; zero pending is not proof of cache hits or zero shader stalls.") }
        return Status(code: "ready", message: "Inspection succeeded: \(pending) captured pipelines pending. Stop/export any running test, then use Pause game and prepare captured pipelines. Preparation adds work; benefit remains unverified.")
    }
    static func preparationBlocker(running: Bool, exporting: Bool, preparing: Bool,
                                   gameVisible: Bool, active: Bool) -> String? {
        if preparing { return "Preparation is already running. Wait for the receipt." }
        if running { return "Stop the lightweight test and export its files before preparing pipelines." }
        if exporting { return "Wait for the current export to finish before preparing pipelines." }
        if !gameVisible { return "No attached game view. Open diagnostics from the running game's bar; preparation cannot start from the library alone." }
        if !active { return "Husk must be in the foreground before preparation can start." }
        return nil
    }
}
