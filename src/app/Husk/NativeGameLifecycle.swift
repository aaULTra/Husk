// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation

/// One attached game view, with independent app and owning-scene visibility.
/// UIKit reparenting is coalesced by the view before publishing attachment.
struct NativeGameLifecycle {
    private(set) var lastPaused: Bool?
    mutating func update(attached: Bool, appActive: Bool, sceneActive: Bool, force: Bool = false) -> Bool? {
        let paused = !attached || !appActive || !sceneActive
        guard force || lastPaused != paused else { return nil }
        lastPaused = paused
        return paused
    }
}

/// Fixed-size interruption history survives an unclean end, including inactive
/// transitions. It records context; it cannot identify watchdogs, jetsam or a
/// deliberate app-switcher termination without the operating system's report.
struct RunningGameSession: Encodable {
    struct Event: Codable { let time: Double; let name: String }
    let schema = 2
    let id: String
    let label: String
    let time: Double
    let build: String
    let session: String
    private(set) var lastState = "starting"
    private(set) var events: [Event] = []
    init(id: String, label: String, build: String, time: Double) {
        self.id = id; self.label = label; self.build = build; self.time = time
        session = UUID().uuidString
        note("starting", time: time)
    }
    mutating func note(_ name: String, time: Double) {
        guard time.isFinite else { return }
        lastState = String(name.prefix(120))
        events.append(Event(time: time, name: lastState))
        if events.count > 32 { events.removeFirst(events.count - 32) }
    }
}
