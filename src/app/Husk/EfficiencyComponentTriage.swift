// SPDX-License-Identifier: GPL-2.0-or-later
import Foundation
import CoreFoundation

/// Pure interpretation of bounded exported evidence. Never changes controls,
/// passes roadmap gates, sums overlapping scopes or diagnoses an exact cause.
enum EfficiencyComponentTriage {
    private static func object(_ x: Any?) -> [String: Any] { x as? [String: Any] ?? [:] }
    private static func rows(_ x: Any?) -> [[String: Any]] { x as? [[String: Any]] ?? [] }
    private static func number(_ x: Any?) -> Double? {
        guard let n = x as? NSNumber, CFGetTypeID(n) != CFBooleanGetTypeID(), n.doubleValue.isFinite, n.doubleValue >= 0 else { return nil }
        return n.doubleValue
    }
    static func build(_ report: [String: Any]) -> [String: Any] {
        let summary = object(report["summary"]), components = object(report["component_sampling"])
        let driver = object(report["driver_phases"]), archive = object(report["native_pipeline_archive"])
        var findings: [[String: Any]] = [], coverage: [[String: Any]] = []
        func add(_ component: String, _ plans: [String], _ confidence: String, _ observation: String, _ next: String, _ evidence: [String: Any]) {
            if findings.count < 64 { findings.append(["component": component, "plan_ids": plans, "confidence": confidence, "observation": observation, "next_action": next, "evidence": evidence]) }
        }
        let losses = ["dropped_frame_intervals_cumulative", "dropped_host_records_cumulative", "dropped_events_cumulative"].reduce(0.0) { $0 + (number(summary[$1]) ?? 0) }
        if losses > 0 || (number(report["dropped_export_records"]) ?? 0) > 0 {
            add("measurement_coverage", ["M1"], "OBSERVATION", "Collector/export losses limit attribution; absent events cannot rule out work.", "Resolve or quantify coverage before accepting a performance comparison.", ["record_losses": losses, "export_losses": report["dropped_export_records"] ?? NSNull()])
        }
        let slow = number(summary["slow_pipeline_calls"]) ?? 0
        if slow > 0 {
            add("pipeline_creation", ["M2", "M5"], "OBSERVATION", "Long Vulkan pipeline-creation calls were recorded. This is not proof every hitch is compilation.", "Compare the same core-v4 variant first/repeat/restart; inspect native requirement checks and driver library/pipeline phases separately.", ["slow_calls": slow, "worst_host_call_ms": (number(summary["worst_pipeline_ns"]) ?? 0) / 1e6])
        }
        let windows = rows(report["windows"])
        let irregular = windows.filter { w in
            guard (number(w["interval_count"]) ?? 0) >= 30 else { return false }
            return ((number(w["p95_ms"]) ?? 0) > 20 || (number(w["worst_ms"]) ?? 0) > 33.333333)
                && number(w["slow_pipeline_calls"]) == 0
        }
        if !irregular.isEmpty {
            add("non_pipeline_pacing", ["M3", "M4", "M6"], "HYPOTHESIS", "Irregular frame windows have no recorded long pipeline completion. Cross-window/in-flight work can remain.", "Inspect sampled GPU, submit CPU/wall, drawable/encoding phases and native presentation history; do not assume the limiter or GPU is the cause.", ["windows": irregular.count, "scope": "Host cadence, not complete displayed-frame timing"])
        }
        coverage.append(["component": "jni_sync_vulkan_scopes", "status": components["requested"] as? Bool == true ? "SAMPLED_COMPLETED_SCOPES_ONLY" : "DISABLED_OR_UNAVAILABLE", "clock_errors": components["clock_errors"] ?? NSNull(), "dropped_samples": components["dropped_samples"] ?? NSNull(), "boundary_dropped_samples": components["boundary_dropped_samples"] ?? NSNull()])
        for row in rows(components["components"]) {
            guard let calls = number(row["completed_sampled_calls"]), calls > 0,
                  let wall = number(row["sampled_wall_ns"]), let cpu = number(row["sampled_caller_cpu_ns"]) else { continue }
            let component = row["component"] as? String ?? "unknown"
            let waiting = calls >= 4 && wall > 0 && cpu < wall / 4
            add(component, ["M3", "M8"], "OBSERVATION", waiting ? "Sampled wall exceeds caller CPU substantially; waiting/descheduling/other-thread work may contribute." : "Included sampled caller CPU and wall are available; the scope can include useful nested work.", "Compare identical captures; inspect this scope in a trace before changing priorities or removing work. Do not extrapolate deterministic samples into watts or whole-component cost.", ["completed_samples": calls, "mean_sampled_wall_ms_estimated": wall / calls / 1e6, "mean_sampled_caller_cpu_ms_estimated": cpu / calls / 1e6, "caller_cpu_fraction_of_sampled_wall": wall > 0 ? cpu / wall as Any : NSNull(), "scope": "Inclusive scopes overlap. Present includes host pacing; once includes initialization. No total-component cost estimate."])
        }
        coverage.append(["component": "moltenvk_phases", "status": driver["available"] as? Bool == true ? "LAST_ACCEPTED_QUERY_ONLY" : "DISABLED_UNSUPPORTED_OR_NO_QUERY", "invalid_values": driver["invalid_phase_values"] ?? NSNull()])
        if driver["available"] as? Bool == true {
            for phase in rows(driver["phases"]) {
                guard (number(phase["new_calls_since_previous_query"]) ?? 0) > 0,
                      (number(phase["new_total_ms_estimated"]) ?? 0) >= 10 || (number(phase["latest_event_ms"]) ?? 0) >= 16.666667 else { continue }
                add(phase["component"] as? String ?? "driver_activity", ["M2", "M3", "M6", "M8"], "OBSERVATION", "Driver host activity is present in the last accepted query; it can overlap other activities and include lifecycle work.", "Use query timestamps/serial and exclusions to align the activity. Library compilation, encoding, drawable waiting and callback latency require different fixes.", ["query_serial": driver["query_serial"] ?? NSNull(), "previous_query_monotonic_ns": driver["previous_query_monotonic_ns"] ?? NSNull(), "query_monotonic_ns": driver["query_monotonic_ns"] ?? NSNull(), "phase": phase, "scope": "First query is lifetime; latest/max/averages are not per-frame GPU or exclusive CPU durations."])
            }
        }
        if archive["verification_requested"] as? Bool == true {
            add("native_archive_requirement", ["M2", "M5"], "OBSERVATION", "Metal archive-requirement checks were requested. Failed attempts are not necessarily archive misses; normal compilation fallback remains.", "Inspect successful requirement checks versus failures and raw NSError, then compare same variants with verification OFF for benefit/energy.", ["attempts": archive["verification_attempts"] ?? NSNull(), "satisfied_calls": archive["metal_archive_requirement_satisfied_calls"] ?? NSNull(), "failed_calls": archive["verification_failed_calls"] ?? NSNull(), "last_error_domain": archive["last_verification_error_domain"] ?? NSNull(), "last_error_code": archive["last_verification_error_code"] ?? NSNull()])
        }
        let queue = object(report["queue_execution_options"]), waits = object(report["initialization_waits"])
        if queue["environment_applied"] as? Bool == true && queue["actual_configuration_available"] as? Bool != true {
            add("queue_configuration", ["M6", "M8"], "OBSERVATION", "Queue options were prepared but actual runtime configuration is unavailable.", "Check driver API/result and restart; requested settings alone cannot establish an applied queue treatment.", queue)
        }
        if waits["requested"] as? Bool == true {
            let observed = number(waits["wait_entries_since_launch"]) ?? 0
            add("initialization_parking", ["M8", "M3"], "OBSERVATION", observed > 0 ? "Parked initialization waits were observed since launch; active polling is bypassed for those waits." : "No parked initialization waits were observed; no saving opportunity demonstrated.", "Separate startup/excluded work from gameplay and compare CPU and wall with the option OFF. Counts alone do not establish power or cooling.", waits)
        }
        let gpu = object(report["gpu_sampling"]), gpuRecords = (report["gpu_records"] as? [Any])?.count ?? 0
        coverage.append(["component": "gpu_execution", "status": gpuRecords > 0 ? "PARTIAL_COMMAND_BUFFER_TIMESTAMPS" : "DISABLED_UNAVAILABLE_OR_NO_VALID_RECORDS", "retained_records": gpuRecords, "collector": gpu])
        let meta = object(report["metadata"])
        coverage.append(["component": "cpu_threads", "status": meta["cpu_thread_sampling_requested"] as? Bool == true ? "SAMPLED_COUNTERS_REQUIRE_IDENTITY_AND_EXCLUSION_AUDIT" : "DISABLED_OR_UNAVAILABLE"])
        coverage.append(["component": "displayed_frames_power_temperature", "status": "LIMITED_OR_EXTERNAL", "scope": "Host/native timing is not complete display accounting. Electrical power and numerical temperature require supported external evidence; thermal state is classification."])
        return ["schema_version": 1, "rule_version": "component-triage-v1", "plan_ids": ["M1", "M2", "M3", "M5", "M6", "M8"],
                "findings": findings, "coverage": coverage, "root_cause_confirmed": false,
                "automatically_passed_roadmap_gates": [String](), "energy_improvement": "UNVERIFIED",
                "scope": "Observations and next investigation targets, not automatic root-cause or bottleneck verdicts. No overlapping durations summed. Zero/unavailable samples never establish zero cost."]
    }
    static func text(_ triage: [String: Any]) -> String {
        let findings = rows(triage["findings"])
        if findings.isEmpty { return "Component triage: no actionable observation in available coverage; this does not establish no problem." }
        return (["Component observations / investigation targets (causes unconfirmed):"] + findings.prefix(12).map { row in
            let plans = (row["plan_ids"] as? [String] ?? []).joined(separator: "/")
            return "[\(plans) \(row["component"] as? String ?? "unknown")] \(row["observation"] as? String ?? "Unavailable") Next: \(row["next_action"] as? String ?? "Review coverage")"
        }).joined(separator: "\n")
    }
}
