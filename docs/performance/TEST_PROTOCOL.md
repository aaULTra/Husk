# Husk performance and efficiency test protocol

See [standing instructions](../../AGENTS.md), [roadmap](../../PROJECT_PLAN.md) and [evidence register](EVIDENCE.md). Implementation readiness and measured benefit are separate gates.

## 1. Baseline and conditions

Use M4 reference 2128 × 1600, Dungeons V1.4, Sharp / Efficient, 60 FPS, Balanced, Driver Default, persistent cache on, detailed profiling off, LPM off. Fully restart after launch-setting changes. Record actual swapchain dimensions, selected settings and binary SHA; selected resolution is not proof of internal scene resolution.

Match scene/route/events, orientation, brightness, display refresh configuration, case/accessories, charging state, ambient and starting surface temperature. Cool near the same starting temperature between sessions. Charging and unplugged sessions are separate strata. Alternate A/B order to limit drift; repeat important comparisons at least three times. Keep cold-cache, same-run repeat and persisted-cache restart results separate. Preserve the working cache before intentional cold-cache experiments.

## 2. Collection contract

Efficiency Test is optional start/stop/export. Preserve the normal rendering behaviour. Lightweight monitoring and Detailed Driver Profiling are distinct controls; never enable the latter automatically.

| Data | Collection | Interpretation |
| --- | --- | --- |
| Frame intervals/FPS | Continuous bounded aggregation; approximately 10-second summaries | Host production/present cadence unless actual displayed timing is available |
| p50/p95/p99, maximum, counts >20/>33.33/>50 ms | Per-window and valid-session aggregation | Specify percentile method and sample counts; do not average percentiles |
| Vulkan acquire/submit/present and host sleep | Reuse existing duration/call counters | Host time; overlapping durations not additive |
| Pipeline events/cache | Bounded slow events and aggregate counters | Identify batch versus per-pipeline time; cache presence/seed acceptance not hits |
| Process CPU | Approximately every 2 seconds | Delta process CPU seconds / active wall seconds; label 100% as one logical CPU, optionally report capacity normalisation separately |
| Memory | Approximately every 10 seconds | Footprint, peak if available, available memory/jetsam are distinct |
| Battery | Start/end, approximately 30 seconds and changes | Supported UIKit level/state; unknown readings remain unavailable |
| Thermal/LPM | Changes and periodic sample | Thermal status classification, not degrees Celsius |
| Display/configuration | Start/change | Brightness, resolution/refresh and launch settings; requests versus actual values |
| Lifecycle/worker/cache state | Event driven | Timestamps, applied versus requested QoS, rollback reasons and restore/checkpoint evidence |
| GPU execution | Only validated instrumentation | Completed command-buffer GPU end − start; no queue-idle waits |
| Power/temperature | External tools | Supported Instruments power and consistent surface/ambient measurements |

Use monotonic timestamps for intervals and a wall-clock origin for correlation; label external clock alignment uncertainty. Never reintroduce display-timing clock-domain errors. Paused/background/excluded periods must not pollute active gameplay metrics. Retain exclusion reasons and event context.

Bound retained windows/events, expose capacity/dropped counts and export away from render-critical work. Session export uses a versioned JSON document plus Markdown report containing build/device/configuration, metric units/provenance/status, active duration, distributions, events, exclusions, limitations and raw references. Unknown values are null/unavailable with a reason, never zero substituted for missing data. Preserve raw measurements when marking excluded periods.

## 3. Test scenarios

- Stable gameplay: same mission segment for 15–20 minutes. Record frame distributions, severe events, CPU/memory, thermal and pipeline activity.
- First-use preparation: same inventory/menu/combat event from controlled initial state; repeat in-session, then restart with persisted cache. Compare equivalent cache conditions.
- Monitoring overhead: disabled versus lightweight on at identical settings, detailed profiling off. Check CPU time, pacing, memory growth, export stutter and external power where available. Overhead must be quantified; do not assert negligible impact from implementation design alone.
- Limiter: default engine request plus host limiter versus experimental engine-only mode. Never disable both in the primary comparison; retain thermal safeguards. Measure actual display cadence if possible.
- Submission: Driver Default versus existing async option; no simultaneous worker/prefill/buffer-limit changes.
- Adaptive: Balanced versus Adaptive with identical resolution/cache/submission. Verify qualifying admission, actual worker self-applied QoS changes, rollback and sustained energy. A trial never admitted is not a valid comparison.
- Sustained energy/heat: 30-minute matched sessions, detailed profiling off. Separate game-closed charging reference, gameplay charging and gameplay unplugged. Record ambient/surface baseline and at 5/10/20/30 minutes, plus cooldown.
- Lifecycle: pause/resume, backgrounding, supported fullscreen/window transitions, resolution retention, dirty/unchanged cache checkpoints, input/audio and absence of blank display/device loss.
- Duo: separate unfolded baseline when hardware exists; verify display/chip/capabilities. Later compare supported open/closed modes and warmed-up sustained operation within that device.

Public iPadOS thermal status is not a numerical thermometer. Use consistent contact measurement or carefully controlled infrared emissivity/reference surfaces; never infer chip temperature from surface temperature. Battery percentage-point drain/hour = decrease × 3600 / valid unplugged seconds; it is a coarse ESTIMATED indicator, unsuitable for small claims from one short session.

Where supported, Instruments system power requires an appropriate unplugged/wireless workflow; verify device/OS/tool and LiveContainer process attribution. USB-C input power includes charging and is not CPU/GPU power. Energy per displayed frame requires measured energy and actual delivered-frame count; otherwise label the denominator as host-present throughput and its limitation. MetricKit feasibility, availability and attribution must be checked; periodic reports supplement direct logs.

## 4. Portable/build checks

For future runtime changes, run the relevant existing suites and required CI regressions:
`test_ue4_graphics.py`, `test_ue4_resolution_hook.py`, `test_source_efficiency.py`, `test_thread_policy.py`, `test_vk_frame_timing.py`, `test_pipeline_store.py`, `test_driver_profile.py`, `test_efficiency.py`, `test_efficiency_math.py` under `tests/translation-layer/`.

Add meaningful tests for aggregation/percentiles and threshold boundaries, CPU deltas, unknown battery readings, pause/exclusion/discontinuity handling, bounded retention, JSON export and no baseline setting changes. Pipeline identity tests must cover deterministic identity across handle changes, changed relevant state, incomplete/unsupported state, batch attribution and bounded recording. Feedback must not alter original chains/results or invent supported flags. Test failure paths and object lifetimes.

Use the existing iOS compilation/IPA packaging workflow for device candidates and record exact artifact/SHA. Passing portable tests does not establish Apple runtime behaviour. Documentation-only changes require link/status/diff review; avoid an unnecessary IPA build.

## 5. Adoption gate

Before adoption, record matched repeat results and relevant variability. Define the candidate's primary metric and practical acceptance margin before measuring, using baseline variability and user-perceptible impact. Report inconclusive small differences honestly.

Require preserved visuals/responsiveness, normal approximately 60 FPS, no material p95/p99 regression, no new device loss/artifacts or lifecycle/cache failures. Pipeline work must improve severe-stall metrics and account for total loading/session cost. Reduced confirmed computation may establish less work, but electrical energy benefit remains pending until measured. Temperature comparisons use matched ambient/start conditions. Keep rejected/no-benefit experiments and default restoration instructions.

## M1 candidate-specific checks

See [lightweight monitoring guide](10-lightweight-monitoring.md). Percentiles use bounded histograms, not raw frame storage. Native collector stage order is documented in export. Large intervals are retained unless explicitly excluded; calls spanning exclusion boundaries use completion-time attribution. Validate that the same pause/marker boundaries appear in the report and JSON. Swift CPU/battery/JSON tests run on macOS CI; they do not validate UIKit/Mach or share-sheet behaviour.
