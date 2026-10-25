# Husk master development plan

Updated: 2026-10-25. Status: approved roadmap saved; measurement implementation is next.
Repository: [aaULTra/Husk](https://github.com/aaULTra/Husk). Development: `codex/dungeons-efficient-native`. [PR #4](https://github.com/aaULTra/Husk/pull/4) remains draft; no merge is authorised by this handover.

## 1. Objective, baseline and source of truth

Deliver excellent visuals and smooth sustained 60 FPS with the lowest practical energy use and unnecessary heat. Measure benefit rather than assume it. Read [AGENTS.md](AGENTS.md) before every task.

Protected reference code: `3c2d52c0f26ca9b40796633b169c40fd7f535e7c`.
M4 reference: Dungeons V1.4, 2128 × 1600 Vulkan presentation, Sharp / Efficient, 60 FPS, Balanced, Driver Default, persistent cache on, detailed MoltenVK profiling off for ordinary comparisons, LPM off. Retain V4 and manual configuration. Internal 3D resolution and acceptance of individual cooked CVars remain unverified.

The new 1784 × 1336 result is an additional experiment. It does not replace the reference or prove an energy saving. See [performance evidence](docs/performance/EVIDENCE.md).
The future iPhone Duo is a separate target, pending hardware; supplied hardware descriptions are provisional until verified. Start unfolded, inventory capabilities and build its own baseline. Do not transfer numerical power/temperature results between devices.

This file owns priorities and statuses. Supporting [test protocol](docs/performance/TEST_PROTOCOL.md) and [decision history](docs/performance/DECISIONS.md) retain detail. Earlier docs 07–09 remain technical history; their older TODOs do not override this current inventory.

## 2. Status model and tracking requirements

Each ID below carries separate implementation, correctness, performance and energy states. Use implementation states: research, planned, partial, implemented, rejected. Use validation states: pending, inconclusive, verified-for-conditions, no-benefit-demonstrated, regression. A feature is not a verified optimisation simply because implemented.

Every experiment record must include ID/device, objective, hypothesis/mechanism, source SHA, configuration, dependencies, baseline/candidate/cache state, procedure, raw evidence references, exclusions, results with variability, correctness, energy status, decision and next action. Unknown fields stay unknown. Failed approaches retain reopening conditions. Do not change old results when adding new evidence.

## 3. Current implementation and evidence

Inspection basis: branch head 3c2d52c, PR metadata, graphics/settings, Vulkan wrapper, cache store, worker controller, driver profiler, relevant tests and docs. This was a targeted inspection of relevant subsystems, not validation of all repository code or raw device logs.

| ID | Feature | Implementation/correctness | Device performance evidence | Energy status / next action |
| --- | --- | --- | --- | --- |
| BASE-01 | V4 resolution interception | Implemented; guarded portable-hook tests exist | User reports retained selected presentation through resumes | Unmeasured; protect and separately verify internal scene resolution |
| BASE-02 | Sharp / Efficient and 60 FPS | Implemented; engine request plus host limiter | Sustained smooth approximately 60 FPS reported on M4 | Unmeasured; preserve quality/reference |
| CACHE-01 | Compatible persistent pipeline cache | Implemented; checksum/header guards, fallback, checkpoints and generation tracking | Restored/saved bytes reported; first-use stalls persist | Actual reuse/hitch and energy benefit unverified |
| PIPE-01 | Bounded slow-call diagnostics | Implemented; worst call/window, totals, batch, cache presence, result, lock wait | Expensive calls closely coincide with some stalls | Extend with stable variant identity/feedback; not a cache-hit counter |
| WORK-01 | Balanced policy | Implemented, default; critical roles preserved | Active in supplied runs | Energy benefit unmeasured; baseline comparator |
| WORK-02 | Adaptive Trial | Implemented revised cheap-pipeline admission and self-applied caps/rollback | Real-device admission/application fix not independently verified here | NOT COMPLETE: energy A/B versus Balanced pending |
| SUBMIT-01 | Async submission option | Implemented, experimental; Driver Default retained | No controlled benefit evidence | Pending independent A/B |
| PROF-01 | Detailed MoltenVK profiling | Implemented; strict 1.4.2/private API 43, 1152-byte guard, optional/off | Earlier report contains driver activity data | Adds overhead; no genuine GPU/power measurement |
| MEAS-01 | Efficiency Test sessions/export | Planned; existing cadence/API/thermal observations can be reused | No integrated session/export validation | First implementation priority |
| GPU-01 | Genuine GPU execution timing | Research; current callback latency is not GPU time | Measurement gap | Instruments or safe completed-buffer access |
| UPSCALE-01 | MetalFX spatial upscaling | Research, not wired into Vulkan presenter | None | Separate prototype only after GPU evidence |
| RES-01 | Manual resolution controls | Implemented 65–100%, with heuristics | Two different presentation runs reported | Dynamic GPU-driven resolution remains unimplemented |

Historical PR validation reports 82 passing portable checks and successful iOS compilation/IPA packaging at the reference SHA: [workflow](https://github.com/aaULTra/Husk/actions/runs/40143757823). These results were not rerun during the documentation handover and do not verify energy efficiency.

## 4. Milestones, dependencies and acceptance

| Milestone | Priority / depends on | Engineering deliverable | Physical-device acceptance / exit gate |
| --- | --- | --- | --- |
| M0 Durable handover | P0 | Root instructions, roadmap, evidence, test protocol and decision history | Documentation only; baseline unchanged |
| M1 Measurement foundation | P1 / M0 | Optional lightweight Efficiency Test with bounded aggregation, start/stop, exclusions, Markdown + JSON export; reuse counters | Metric sanity, lifecycle/export correctness and monitoring overhead A/B; no hidden graphics changes |
| M2 Pipeline identification | P1 / M0; integrate with M1 | Stable shader/state diagnostic identity with completeness/version labels; capability-checked creation feedback; bounded event retention/drop counters | Same event first/repeat/restart; demonstrate which variants recur and what reuse evidence actually means |
| M3 GPU and energy baseline | P2 / M1 | Verify feasible GPU timing path; Instruments/power workflow and attribution limits | Real GPU execution, unplugged power where supported, external temperature and repeated M4 reference sessions |
| M4 Non-pipeline pacing | P2 / M1 | Reversible engine-only host-limiter bypass; retain dual-limiter default and thermal protections | Matched distributions/display cadence/CPU work; retain default if no meaningful benefit |
| M5 Selective pipeline preparation | P3 / M2 and representative baseline | Investigate complete replayable creation state; bounded prototype only if safe | Lower gameplay long-call/stall burden, no device loss/artifacts, cache correctness; include loading duration and total session energy |
| M6 Presentation/submission | P3 / M1–M3 | Audit drawable/view/transform/swapchain sizing and suboptimal results; independently test existing async mode | Demonstrated benefit without aspect/quality/input/latency/lifecycle regressions |
| M7 Adaptive efficiency | P3 / repeatable M1–M3 | Reuse controller; close diagnostic gaps only | Confirm admission, actual QoS changes, rollbacks and energy versus Balanced with smoothness preserved |
| M8 Translation and GPU research | P4 / traces from M3 | Profile confirmed encoding/state/resource/allocation/lock costs; synchronisation/frames-in-flight; targeted JNI/Bionic/futex; compatible MoltenVK release benchmarking | One change at a time, correctness, p95/p99 and energy/work evidence |
| M9 Resolution/upscaling | P4 / demonstrated GPU cost | Separate fixed-budget, dynamic resolution and MetalFX spatial investigations; user controls | Perceptual quality plus end-to-end GPU/energy results, including scaler cost; no automatic quality cuts |
| M10 Device profiles | Future / available Duo and M1 | Verified capability-specific profiles, safe unknown-device defaults/manual override | Independent unfolded Duo baseline and sustained tests; no inherited M4 optimum |

M1 instrumentation must precede behavioural optimisation. M2 observation may accompany M1 without changing rendering. M3 evidence may reorder later milestones; preserve all IDs when reprioritising.

### Measurement implementation contract

Optional Game Graphics diagnostics: Lightweight Efficiency Monitoring and separate Detailed Driver Profiling. Do not auto-enable detailed MoltenVK activity tracking. Efficiency Test has explicit start/stop/export and manual interruption markers. Export a concise Markdown summary plus versioned JSON with session/build/device/configuration metadata, time origin, windows, events, exclusions, units, provenance and unavailable reasons.

Aggregate frame intervals without per-frame logs. Sample process CPU at approximately 2 seconds, memory at 10 seconds, battery at 30 seconds and state changes; thermal/lifecycle/configuration/worker/cache events on change. Use existing roughly 10-second Vulkan reporting where practical. Preserve active-interval timing across pause/resume and mark discontinuities. Bound in-memory data and expose dropped samples; export off the render path.

CPU time/activity is process-scoped with explicit normalisation. Track footprint/peak/jetsam separately. Battery drain is an estimate only for valid unplugged intervals. GPU execution remains UNAVAILABLE until safe instrumentation is validated. No invented temperature or watts. Full contract and tests: [protocol](docs/performance/TEST_PROTOCOL.md).

## 5. Outstanding bugs and measurement gaps

| ID | Evidence / status | Next action |
| --- | --- | --- |
| BUG-01 | Severe pipeline-associated hitches persist despite restored cache; new reported worst call 436.954 ms | M2: stable variants and actual supported reuse evidence, first/repeat/restart |
| BUG-02 | Approximately 33 ms irregularities reported with zero pipeline calls | M1/M3/M4: correlate CPU/GPU/presentation/limiter data; cause unknown |
| BUG-03 | Repeated VK_SUBOPTIMAL_KHR and view-size changes | M6: inspect pixel drawable versus point bounds/transforms; nonfatal, cost unproven |
| GAP-01 | No measured watts, electrical energy, true GPU execution or numerical device temperature | M3 and external measurements |
| GAP-02 | No controlled baseline/candidate energy comparison | M1/M3 before efficiency claims |
| GAP-03 | Internal render resolution/CVar acceptance unknown | Capture/engine evidence without weakening V4 |
| GAP-04 | Supplied raw device logs unavailable in this handover | Obtain complete exports in next physical test; preserve reported evidence labels |
| COMPAT-01 | isnan/JNI/optional OBB/ANGLE warnings not demonstrated performance causes | Investigate only with malfunction or traceable cost |

## 6. Next actions and task handover

Next engineering task: M1 measurement foundation, beginning with a fresh source audit of lifecycle, UI/export plumbing and available telemetry; add no optimisation toggles in that patch. M2 then extends existing slow-call support instead of duplicating it. Obtain M4 baseline evidence with monitoring overhead separated, then prioritise measured costs.

Physical iPad tasks: export raw first/repeat/restart logs; validate lightweight reports; run matched monitoring-off/on baseline; gather unplugged power if tooling supports it and surface/ambient temperatures; later perform limiter, submission and Adaptive A/B separately.

2026-10-25: User approved the structured plan and authorised saving it to GitHub. M0 documents prepared from the targeted repository inspection and supplied Sections 1–19/new-run summary. No runtime source, defaults, cache files or graphics settings changed. No device tests performed. M1–M10 remain open; all energy claims pending.

At each handover append dated implementation/evidence/decision updates here and in the linked records. Do not close a milestone whose physical-device gate is pending.
