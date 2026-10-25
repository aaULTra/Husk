# M1: Lightweight efficiency test candidate

Sequence: M0 permanent plan -> **M1 / MEAS-01 collection and export** -> M2 pipeline identity/reuse -> M3 actual GPU/power/temperature -> evidence-led optimisation. See [master plan](../../PROJECT_PLAN.md). This feature collects observations; it is not a demonstrated optimisation.

## Use

Open Game Graphics > Performance & Efficiency Diagnostics, or the gauge button in the fullscreen UE4 game bar. Three fingers restore a hidden interface. Start a lightweight test, then dismiss the panel and play. The panel, inactive application time and detached game views are excluded. The manual interruption toggle excludes other deliberate actions until cleared. No graphics setting is changed.

Stop the test, export, then share both report.md and diagnostics.json. Files are also under Files > Husk > EfficiencyTests/<session directory>. Export before force-quitting: capture is in-memory, with no crash persistence. Starting a new test replaces the in-memory session but not previously exported files. Nothing is sent automatically.

Keep Detailed Driver Profiling off for ordinary comparisons. It remains a separate setting requiring restart; if enabled, its detailed MoltenVK counters stay in the attempt log. Attach that log separately for driver analysis. Starting lightweight monitoring never enables driver profiling.

## Schema and interpretation

Schema version 1 exports metadata, summary, approximately 10-second windows, approximately 2-second samples, events, exclusion ranges, duration, battery estimate and dropped-record counts. Session-relative times use CLOCK_MONOTONIC, with UTC/monotonic origin in metadata. Build identity comes from packaged Info.plist; unknown/unpackaged identity is labelled unavailable. Configuration comes from actual launch parameters, not subsequently edited settings.

Host stage order: acquire, submit, present, host sleep, graphics pipeline creation, compute pipeline creation. Calls may overlap and sum above elapsed time. Pipeline counts are API/batch calls, not individual pipelines; slow means >=16.666667 ms. A call spanning an exclusion is attributed at completion. Selected existing cache/worker/pipeline messages retain text (bounded to 511 bytes), not structured cache-hit proof or full shader identities. Those are M2 work.

Frame cadence is post-presentation/post-pacing host cadence from the Sharp Vulkan path, not physical display timing or GPU execution. Histograms have 0.1 ms upper bins through approximately 1 second; overflow percentiles use the exact observed maximum as a conservative bound. Counts, interval sum and maximum retain multi-second hitches. Percentiles are ESTIMATED and calculated over the session histogram, never averaged from window percentiles. Empty distributions export nulls.

Process CPU uses live plus terminated thread CPU time and 100% means one logical CPU. LiveContainer may include host work. Mach footprint and jetsam headroom are distinct; peak footprint is unavailable. Thermal classification is not degrees Celsius. Battery drain is a coarse estimate over observed included unplugged intervals; unknown/charging states and exclusions reset its anchor.

Capacity: 1,440 exported windows, 7,200 samples, 2,048 events/exclusions and a 256-entry native event queue. Later records beyond export capacity are dropped and disclosed; total collector aggregates remain available. The frame/call observation path uses try-locks and skips contended diagnostics rather than waiting; drops reset cadence continuity and are counted. An event capture is bounded, not a complete trace. No queue waits/readbacks or per-frame file writes are introduced.

## Physical-device acceptance still required

1. Install the exact successfully built candidate; check full SHA in export.
2. Confirm actual 2128 × 1600, Sharp / Efficient, 60 FPS, Balanced, Driver Default, persistent cache and profiling off.
3. Start before a repeated mission segment. Verify CPU/footprint, battery state, thermal classification and swapchain size are plausible; no fabricated GPU/power/temperature values appear.
4. Mark an intentional interruption, clear it, pause/resume and open/close the panel. Verify exclusion ranges, continuity, retained surrounding events and sensible CPU/battery anchors.
5. Stop/export/share both files. Test a second session and export failure handling. Verify input/audio and resolution retention after all panel/lifecycle operations.
6. Compare monitoring disabled versus on using matched gameplay and conditions, at least three repeats. Quantify CPU/p95/p99/memory and external power overhead; do not assume it is negligible. Test 30-minute sessions and bounded memory behaviour.
7. Attach raw attempt log for first/repeated/restarted pipeline events. Stable variant identity and creation feedback remain M2, not implemented here.

No real-device correctness, energy saving or heat reduction has been verified by portable tests or an IPA build. M1 stays open until this checklist and monitoring-overhead experiment have evidence.

## Built candidate

Source: `1a68f40a377be7a8d0feac1bf05b6170d87659b9`. [Successful build](https://github.com/aaULTra/Husk/actions/runs/40163119357), [IPA artifact](https://github.com/aaULTra/Husk/actions/runs/40163119357/artifacts/12586749378). All 92 checks passed. The packaged SHA includes `-dirty` from the existing release-resource staging/project regeneration; retain that exact identity in device evidence. Follow-up documentation-only commits do not change this binary. This is a testing candidate; M1's device gate is still open.

## Schema v2 refinement candidate

M1/MON-01: 8,192-slot bounded frame ring removes reporting-mutex contention from frame collection. Host/event losses do not reset cadence. True frame enqueue losses have separate counts and lost-duration/max fields; frame_distribution_complete is false when any are recorded. Histograms contain retained intervals, and the lost maximum remains separately visible. Multiple producer threads have separate interval anchors; host cadence is not display timing.

M1/MON-02: unchanged valid battery levels export null rate with UNRESOLVED status, observed level change, sample count and valid duration. Increasing unplugged readings are inconclusive. Human reports include observed CPU maximum, sampled footprint maximum and thermal classifications.

Use Phase marker to label Loading, Menu, Gameplay, First-use effect and Repeated effect. Phase changes are events, not automatic engine-state detection; samples carry the latest marker. Event plan_ids/subsystem/outcome and benefit_validation make roadmap association explicit. recorded_t is capture time, occurred_t is supplied only when an existing diagnostic includes an actual completion timestamp. Phase at an occurrence can be reconstructed from phase events; it must not be guessed from report time.
