// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation

enum RuntimeLogEvidence {
    static func currentLines(_ text: String) -> [String] {
        // Husk replays older native lines with [prev]. Those are historical
        // context, never evidence that this particular run failed the same way.
        text.split(separator: "\n", omittingEmptySubsequences: true).map(String.init).filter { !$0.contains("[prev]") }
    }
    static func fatalSignal(_ lines: [String]) -> Int? {
        for line in lines.reversed() {
            guard line.contains("*** FATAL SIGNAL") || line.contains("=== FATAL signal") || line.contains("=== CRASH:") else { continue }
            guard let range = line.range(of: "signal\\s+[0-9]+", options: [.regularExpression, .caseInsensitive]),
                  let number = line[range].split(whereSeparator: { $0.isWhitespace }).last else { continue }
            if let signal = Int(number), (1...64).contains(signal) { return signal }
        }
        return nil
    }
    static func requiredOBBStartupFailure(_ lines: [String]) -> String? {
        let startupFailed = lines.contains { $0.contains("the game could not be started") || $0.contains("native: launch refused") }
        guard startupFailed else { return nil }
        for line in lines where line.contains("alive:") {
            if let range = line.range(of: "alive:\\s+[0-9]+", options: .regularExpression),
               let count = line[range].split(whereSeparator: { $0.isWhitespace }).last.flatMap({ Int($0) }), count > 1 { return nil }
        }
        return lines.first { line in
            guard line.contains("expansion file (OBB) is missing") else { return false }
            let name = line.split(separator: "/").last.map(String.init) ?? ""
            return name.hasPrefix("main.") && name.hasSuffix(".obb")
        }
    }
}
