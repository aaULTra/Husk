// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation
import CoreGraphics

/// UIKit has already inverted the view transform. Map its local bounds to the
/// fixed launch output; UE4 applies the optional spatial input scale afterwards.
enum NativeTouchCoordinates {
    static func map(_ point: CGPoint, bounds: CGRect, surface: CGSize) -> CGPoint? {
        guard point.x.isFinite, point.y.isFinite, bounds.minX.isFinite, bounds.minY.isFinite,
              bounds.width.isFinite, bounds.height.isFinite, bounds.width > 0, bounds.height > 0,
              surface.width.isFinite, surface.height.isFinite, surface.width > 0, surface.height > 0 else { return nil }
        let x = (point.x - bounds.minX) / bounds.width * surface.width
        let y = (point.y - bounds.minY) / bounds.height * surface.height
        guard x.isFinite, y.isFinite, abs(x) <= CGFloat(Float.greatestFiniteMagnitude),
              abs(y) <= CGFloat(Float.greatestFiniteMagnitude) else { return nil }
        return CGPoint(x: x, y: y)
    }
}
