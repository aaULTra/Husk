// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation

/// Keep early context and a bounded chronological tail without moving an array
/// on each append. Full aggregate counters are collected separately.
struct BoundedRecordHistory<Row> {
    let firstLimit: Int
    let recentLimit: Int
    private(set) var first: [Row] = []
    private var ring: [Row] = []
    private var next = 0
    private(set) var observed = 0
    init(firstLimit: Int, recentLimit: Int) {
        precondition(firstLimit >= 0 && recentLimit >= 0)
        self.firstLimit = firstLimit; self.recentLimit = recentLimit
    }
    mutating func append(_ row: Row) {
        observed += 1
        if first.count < firstLimit { first.append(row); return }
        guard recentLimit > 0 else { return }
        if ring.count < recentLimit { ring.append(row) }
        else { ring[next] = row; next = (next + 1) % recentLimit }
    }
    var recent: [Row] {
        guard ring.count == recentLimit, next > 0 else { return ring }
        return Array(ring[next...]) + Array(ring[..<next])
    }
    var omitted: Int { observed - first.count - ring.count }
    var retained: Int { first.count + ring.count }
}
