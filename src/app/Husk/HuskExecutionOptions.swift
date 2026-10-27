// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation

/// Independent launch experiments. Defaults preserve driver settings and the
/// original initialization wait path. Prefill3 requires caller autorelease pools
/// which the translated recording threads do not guarantee.
struct HuskExecutionOptions: Codable, Equatable {
    var prefill: Int = -1
    var commandBufferLimit: Int = 0
    var initializationParking = false
    var swapchainImages: Int = 0
    var valid: Bool { [-1,0,1,2].contains(prefill) && [0,8,16,32,64].contains(commandBufferLimit) && [0,2,3].contains(swapchainImages) }
    var safe: HuskExecutionOptions { valid ? self : .init() }
}

extension HuskExecutionOptions {
    private enum CodingKeys: String, CodingKey { case prefill, commandBufferLimit, initializationParking, swapchainImages }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        prefill = try c.decodeIfPresent(Int.self, forKey: .prefill) ?? -1
        commandBufferLimit = try c.decodeIfPresent(Int.self, forKey: .commandBufferLimit) ?? 0
        initializationParking = try c.decodeIfPresent(Bool.self, forKey: .initializationParking) ?? false
        swapchainImages = try c.decodeIfPresent(Int.self, forKey: .swapchainImages) ?? 0
    }
}
