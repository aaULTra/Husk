# E-M4-003 — JSON audit

## Source and scope

Parsed the uploaded diagnostics.json as data, not instructions. Archive: [original JSON](E-M4-003.diagnostics.json). SHA256: `c83febcc9c055d87c3da0fabe9f10d79e8960387a5839f671eb2e218ed925c5f`, 130,452 bytes. Session `4F2090D5-8746-446A-95FD-68FB01D2F52B`; start 2026-10-25 05:10:21 UTC (05:10:21 Europe/London on this date). Source build 1a68f40a377be7a8d0feac1bf05b6170d87659b9-dirty. See [original report/log record](E-M4-003.md).

This task audits evidence and updates the roadmap. It changes no runtime code or settings and makes no energy-saving claim.

## Reconciliation checks

All checked summary fields reconcile with the 37 exported windows: interval count and summed duration; >20/>33.333333/>50 ms counts; slow pipeline-call count; all six host-call counts and durations; frame and pipeline maxima. FPS equals interval_count / interval_seconds. No export records were dropped. There are 204 process/environment samples and 71 events.

| Quantity | Result |
| --- | --- |
| Session wall duration | 405.467942 s |
| Three exclusion spans, all game-view-detached | 16.537365 s total |
| Wall duration less recorded exclusions | 388.930577 s |
| Retained frame-interval duration | 385.228790 s |
| Retained intervals | 21,350 |
| Host cadence | 55.421611 FPS |
| Estimated p50/p95/p99 | 16.7 / 20.9 / 21.1 ms |
| >20 ms | 6,087 intervals, 28.5105% of retained intervals |
| >33.333333 / >50 ms | 31 / 28 intervals |
| Slow pipeline API/batch calls | 69 |
| Worst retained interval / pipeline call | 587.229 / 312.790 ms |
| Graphics pipeline host time | 9,543.963 ms over 480 calls (overlap possible) |
| Native collector/export drops | 6 / 0 |

Retained intervals and wall duration differ because of startup without a pair of presents, exclusion/continuity boundaries and lossy observations. Arithmetic consistency does not establish complete frame coverage. The window schedule is roughly 10–12 seconds, and an interval can span a window boundary; do not expect each interval-duration sum to equal its nominal window width.

The session includes engine startup: visibility is included at t=3.659 s, before captured launch parameters and first swapchain at t=4.594 s. There is no explicit loading/menu/mission marker. Do not label all included time as stable mission gameplay.

## Battery, display, thermal and process evidence

All 15 battery samples report level 0.699999988079071 (approximately 70%) and state 1 (unplugged). The estimator accumulated 309.853644 valid seconds, with zero reported decrease. Its zero result is arithmetically explained; it is not zero energy or proof of good efficiency. The interval is short/coarse, and freshness/accuracy of the native reading in this hosted environment is unvalidated. Cross-check against the system indicator on a future test before trusting drain comparisons. Do not declare a battery API bug solely from this plateau.

Brightness is 1.0 (100%) throughout the 204 environment samples. Thermal classification is 0 and LPM false throughout. maximum_refresh_hz=120 is the screen capability, not measured current refresh rate. Keep brightness matched in comparisons; no measured subsystem power attribution is available.

CPU activity: 193 non-null interval estimates. Duration-weighted mean 63.0491% of one logical CPU over 386.210569 sampled seconds; median approximately 61.8391%; highest sampled interval 228.3210% near t=6.071 s during startup. Formula: sum(sample_percentage × preceding sample wall interval) / sum(valid sample wall intervals). CPU time is process-scoped, potentially including LiveContainer host work. This is not device-wide utilisation, core placement, electrical power or proof of GPU limitation.

Footprint rises from approximately 0.577 GiB before launch to approximately 2.7 GiB, then approximately 3.55 GiB around t=134–146 s. From t=150–390 s it ranges approximately 3.544–3.592 GiB. Maximum observed footprint is 3.592244 GiB; minimum sampled jetsam headroom is 12.407756 GiB. Footprint falls to 3.484 GiB after the final detach. This short loading/asset-related growth followed by a plateau is not proof of a leak or exhaustion. Actual peak footprint remains unavailable.

## Pipeline and non-pipeline paths

- t=122.197–134.198 s: worst frame interval 245.039 ms, worst pipeline call 243.308 ms, five slow pipeline calls. Supports a pipeline-associated hitch, without exclusive attribution.
- t=112.178–122.197 s: worst interval 587.229 ms, three graphics calls totalling 23.442 ms, worst call 11.567 ms, zero slow calls. The differently aligned legacy log window reports 0.317 ms; both agree no approximately 587 ms compilation call is recorded. This is not explained by the recorded long-pipeline mechanism.
- t=10.010–20.200 s: worst interval 410.722 ms, worst pipeline call 1.517 ms, zero slow calls.
- t=332.062–342.132 s: approximately 51.02 FPS, maximum interval 21.003 ms, pipeline maximum 1.087 ms. Frequent slower cadence also occurs without severe shader stalls.
- t=44.196–56.196 s: 24 slow pipeline calls, maximum 312.790 ms, but retained frame maximum only 21.262 ms; native drops rise from 3 to 5.
- t=244.225–256.037 s: one 135.277 ms pipeline call, but retained frame maximum 21.152 ms; native drops rise from 5 to 6.

Pipeline calls may run on non-critical threads. Also, this collector's enter() sets a global gap flag on any observation-lock contention; tl_em_frame() then resets its previous timestamp. A lost host/event observation can consequently remove a valid cadence interval. The six drops cannot be categorised from this schema. Do not equate every slow pipeline call with a visible hitch or assume retained maxima cover all hitches. The JSON cannot tell which mechanism accounts for the mismatched windows. This is a confirmed measurement-policy limitation requiring M1 refinement, not evidence that the renderer regressed.

Runtime event t is capture/report time; a pipeline detail's embedded finished monotonic timestamp is its completion time. Subtract metadata.monotonic_origin_seconds to correlate completion with windows. Do not treat periodic report time as call completion.

## Gates and sequential actions

M0 -> **M1: arithmetic/export validated on this supplied session; cadence coverage, battery freshness, intentional marker/lifecycle coverage and overhead remain open** -> M2 pipeline identity/cache effectiveness -> M3 CPU/GPU/power trace and M4 independent limiter test -> targeted optimisations.

1. M1 / MON-01: separate frame/API/event loss counters; prevent unrelated diagnostic loss from silently resetting valid frame timing; represent genuinely lost intervals/coverage explicitly. Test contention, long stalls, exclusion boundaries and per-window reconciliation. Preserve nonblocking rendering observation.
2. M1 / MON-02: distinguish unchanged reported battery level from verified zero drain; report sample span/count/level change and uncertainty. Validate native readings against the system indicator. Do not fabricate watts.
3. M1: explicitly mark loading/menu/mission periods, show observed footprint/CPU/battery context in the human report, and disambiguate event report time versus occurrence time. Device marker/lifecycle and monitoring-off/on tests remain necessary.
4. M2: reuse this foundation to identify variants and supported cache feedback; no indiscriminate prewarming. All 69 slow calls are tracked, not automatically classified as 69 gameplay hitches.
5. M3/M4: investigate the separate non-pipeline cadence/stall path with real execution/presentation evidence and reversible limiter comparison. No automatic resolution, worker or submission change follows from this audit.
6. Adaptive Trial energy validation, driver benchmarking, dynamic resolution and MetalFX remain open. Keep the 2128 × 1600/Balanced reference intact.

No additional user test is required before engineering these targeted M1 collection/reporting refinements. Another broad benchmark with the same lossy policy would not resolve its coverage uncertainty.
