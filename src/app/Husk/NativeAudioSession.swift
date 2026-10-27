// SPDX-License-Identifier: GPL-2.0-or-later
import AVFoundation
import UIKit

/// Recover the native runtime's output after OS audio events. Visibility remains
/// owned by the game's lifecycle; recovery cannot resume a hidden game.
@MainActor
final class NativeAudioSession {
    static let shared = NativeAudioSession()
    private var interruptionInProgress = false
    private var observers: [NSObjectProtocol] = []
    private let worker = DispatchQueue(label: "com.husk.native-audio-recovery", qos: .utility)
    private init() {}

    func start() {
        guard observers.isEmpty else { return }
        for name in [AVAudioSession.interruptionNotification, AVAudioSession.mediaServicesWereResetNotification,
                     AVAudioSession.routeChangeNotification, UIApplication.didBecomeActiveNotification] {
            observers.append(NotificationCenter.default.addObserver(forName: name, object: nil, queue: .main) { [weak self] note in
                MainActor.assumeIsolated { self?.handle(note) }
            })
        }
    }
    private func handle(_ note: Notification) {
        let state = husk_unity_state()
        guard state == Int32(HUSK_UNITY_RUNNING) || state == Int32(HUSK_UNITY_STARTING) else { return }
        if note.name == AVAudioSession.interruptionNotification {
            guard let raw = note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
                  let type = AVAudioSession.InterruptionType(rawValue: raw) else { return }
            if type == .began {
                interruptionInProgress = true
                worker.async { husk_unity_audio_interrupted(true) }
                return
            }
            interruptionInProgress = false
            let options = AVAudioSession.InterruptionOptions(rawValue: note.userInfo?[AVAudioSessionInterruptionOptionKey] as? UInt ?? 0)
            guard options.contains(.shouldResume) else { return }
        } else if note.name == AVAudioSession.routeChangeNotification {
            guard let raw = note.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt,
                  let reason = AVAudioSession.RouteChangeReason(rawValue: raw),
                  [.newDeviceAvailable, .oldDeviceUnavailable, .wakeFromSleep, .noSuitableRouteForCategory].contains(reason) else { return }
            // Ignore category-change notifications caused by our own activation.
        }
        guard !interruptionInProgress else { return }
        let forceRebuild = note.name == AVAudioSession.mediaServicesWereResetNotification || note.name == AVAudioSession.routeChangeNotification
        let reason = note.name.rawValue
        worker.async {
            let session = AVAudioSession.sharedInstance()
            do {
                try session.setCategory(.playback, mode: .default, options: [.mixWithOthers])
                try session.setActive(true)
                husk_unity_audio_interrupted(false)
                husk_unity_audio_recover(forceRebuild)
            } catch {
                HuskLog.log("audio", "native output activation failed after \(reason): \(error.localizedDescription)")
            }
        }
    }
}
