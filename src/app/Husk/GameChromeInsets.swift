// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation

/// UI-01 / M1 / M6. Compute *additional* clearance in the overlay's coordinates,
/// so a hosting view that already respects safe areas is not inset a second time.
struct GameChromeClearance: Equatable {
    var top: CGFloat = 0
    var leading: CGFloat = 0
    var trailing: CGFloat = 0
}
enum GameChromeLayout {
    static func clearance(view: CGRect, safe: CGRect, status: CGRect?, hostedTopBoundary: CGFloat?) -> GameChromeClearance {
        guard view.width > 0, view.height > 0, view.minX.isFinite, view.minY.isFinite,
              view.maxX.isFinite, view.maxY.isFinite else { return GameChromeClearance() }
        var top: CGFloat = 0, left: CGFloat = 0, right: CGFloat = 0
        if safe.width > 0, safe.height > 0, safe.minX.isFinite, safe.minY.isFinite, safe.maxX.isFinite {
            top = max(0, safe.minY - view.minY)
            left = max(0, safe.minX - view.minX)
            right = max(0, view.maxX - safe.maxX)
        }
        if let status, !status.isEmpty, status.intersects(view), status.maxY.isFinite {
            top = max(top, status.maxY - view.minY)
        }
        if let boundary = hostedTopBoundary, boundary.isFinite {
            top = max(top, boundary - view.minY)
        }
        return GameChromeClearance(top: min(view.height, max(0, top)),
                                   leading: min(view.width, max(0, left)),
                                   trailing: min(view.width, max(0, right)))
    }
}

#if canImport(UIKit) && canImport(SwiftUI)
import UIKit
import SwiftUI

/// Reads the actual attached window, not an arbitrary UIApplication key window.
/// Event-driven only; never touches the game's view/layer or rendering size.
struct GameChromeInsetsReader: UIViewRepresentable {
    var onChange: (GameChromeClearance) -> Void
    func makeUIView(context: Context) -> GameChromeProbe {
        let view = GameChromeProbe(frame: .zero); view.onChange = onChange; return view
    }
    func updateUIView(_ view: GameChromeProbe, context: Context) {
        view.onChange = onChange
    }
    static func dismantleUIView(_ view: GameChromeProbe, coordinator: ()) { view.detach() }
}
final class GameChromeProbe: UIView {
    var onChange: ((GameChromeClearance) -> Void)?
    private var observers: [NSObjectProtocol] = []
    private var last: GameChromeClearance?
    private var refreshPending = false
    override init(frame: CGRect) {
        super.init(frame: frame); isUserInteractionEnabled = false; isAccessibilityElement = false
        backgroundColor = .clear
    }
    required init?(coder: NSCoder) { fatalError("not used") }
    override func didMoveToWindow() {
        super.didMoveToWindow(); removeObservers()
        guard window != nil else { last = nil; return }
        let nc = NotificationCenter.default
        for name in [UIApplication.didChangeStatusBarFrameNotification,
                     UIApplication.didBecomeActiveNotification, UIApplication.willResignActiveNotification,
                     UIWindow.didBecomeKeyNotification, UIDevice.orientationDidChangeNotification] {
            observers.append(nc.addObserver(forName: name, object: nil, queue: .main) { [weak self] _ in
                self?.scheduleRefresh()
            })
        }
        scheduleRefresh()
    }
    override func safeAreaInsetsDidChange() { super.safeAreaInsetsDidChange(); scheduleRefresh() }
    override func layoutSubviews() { super.layoutSubviews(); scheduleRefresh() }
    func scheduleRefresh() {
        guard !refreshPending, window != nil else { return }
        refreshPending = true
        // Defer state publication out of SwiftUI layout/updateUIView.
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }; self.refreshPending = false; self.refresh()
        }
    }
    private func refresh() {
        guard let window else { return }
        // Convert all window/screen geometry into THIS overlay's local points.
        // A hosted guest may itself be scaled or translated by LiveContainer.
        let safe = convert(window.safeAreaLayoutGuide.layoutFrame, from: window)
        var status: CGRect?
        if let manager = window.windowScene?.statusBarManager, !manager.isStatusBarHidden {
            let windowStatus = window.convert(manager.statusBarFrame, from: window.screen.coordinateSpace)
            status = convert(windowStatus, from: window)
        }
        // LiveContainer can keep the host iPad status area visible while the
        // guest reports a hidden status bar/zero inset. Reserve its top strip.
        // Relative-to-window math avoids adding this twice to an already-safe view.
        let hosted = getenv("LC_HOME_PATH") != nil && UIDevice.current.userInterfaceIdiom == .pad
        let reserve: CGFloat? = hosted ? convert(CGPoint(x: window.bounds.midX, y: window.bounds.minY + 24), from: window).y : nil
        let value = GameChromeLayout.clearance(view: bounds, safe: safe,
                                               status: status, hostedTopBoundary: reserve)
        guard value != last else { return }
        last = value; onChange?(value)
    }
    private func removeObservers() {
        observers.forEach { NotificationCenter.default.removeObserver($0) }; observers.removeAll()
    }
    func detach() { removeObservers(); onChange = nil }
    deinit { observers.forEach { NotificationCenter.default.removeObserver($0) } }
}
#endif
