# Husk decision and investigation history

Updated: 2026-10-25. See [master plan](../../PROJECT_PLAN.md).
This is a structured digest of the supplied technical handover Sections 1–19 and repository inspection, not a verbatim copy or independently verified raw-log archive.

## Decisions and previous approaches

| ID | Decision / historical result | Reason and evidence | Reopen when |
| --- | --- | --- | --- |
| D01 | Protect V4 and selected high-resolution reference | Earlier resolution approaches reverted to approximately 816 × 720; newer request/parser interception retained output | Replacement has independently validated engine semantics, aspect ratio and lifecycle tests |
| D02 | Keep Sharp / Efficient, 60 FPS, Balanced and Driver Default | Best documented M4 working configuration; no established energy optimum | A matched device experiment passes correctness, pacing, quality and relevant benefit gates |
| D03 | Extend existing slow diagnostics | Worst-call/totals/cache-presence/lock-wait already implemented | Stable identity/feedback missing; M2 addresses these |
| D04 | Cache restoration is not cache-hit evidence | Accepted persistent seeds coexist with expensive calls | Supported per-pipeline feedback or controlled repeated-event evidence is available |
| D05 | Preserve checkpoint-generation safeguards | Skips unchanged pause snapshots; handles failed saves, concurrent mutation and recycled device handles | A proven replacement preserves all tested guarantees |
| D06 | Adaptive activation fix is implementation only | Previous zero-pipeline admission blocked trials; revised small-cost thresholds are hypotheses | Real admission, applied QoS, rollback and measured energy versus Balanced are established |
| D07 | No assumed core affinity | QoS and runtime CPU count do not establish core placement or per-job energy | Supported trace evidence and safe policy justify a new experiment |
| D08 | Keep dual limiter default pending comparison | Engine t.MaxFPS request, host limiter and FIFO may interact; causation unproven | Independent engine-only comparison demonstrates benefit |
| D09 | Do not reuse mismatched display timestamps | Earlier VK_GOOGLE_display_timing clock-domain issue | Correct domains/alignment are implemented and validated |
| D10 | Distinguish GPU execution and callbacks | MoltenVK reader exposes commit-to-callback latency and overlapping activities | Safe completed-buffer GPU timing or appropriate Instruments capture |
| D11 | Do not blindly shrink swapchain to view bounds | Point bounds, drawable pixels and transforms differ; repeated suboptimal result is usable | Sizing/compositing audit establishes correctness and unnecessary work |
| D12 | Keep async independent | Moving encoding to another queue does not prove less work | Controlled pacing/CPU/energy A/B |
| D13 | No indiscriminate prewarming | Can increase startup energy; full pipeline state/lifetime is required | Identified costly variants with valid preparation path and measured net benefit |
| D14 | Separate MetalFX research | Not implemented; synchronization, textures, formats and UI quality need design; temporal requires extra data | Actual GPU cost justifies spatial feasibility prototype and end-to-end testing |
| D15 | No speculative driver upgrade | Bundled reader pins MoltenVK 1.4.2/private API 43 layout | Compatible stable release tested independently, including ABI/correctness/energy |
| D16 | Do not chase unrelated startup warnings | isnan/JNI/optional OBB/ANGLE presence has no demonstrated causal cost | Observable malfunction or traceable overhead |
| D17 | Measurement before further major optimisation | Smooth play and nominal thermal state coexist with physical warmth; watts unknown | M1/M3 provide a repeatable baseline |
| D18 | Separate hardware targets | iPad is available; Duo is not, and its profile is unverified | Actual Duo hardware supports independent capability inventory and tests |
| D19 | Retain 1784 × 1336 as separate evidence | Approximately 30% fewer presentation pixels and still severe stalls, without controlled energy comparison | Matched quality/energy data supports user-approved profile changes |

## Coverage of the supplied handover

- Sections 1–4: historical progress, reference resolution/cadence/thermal/memory limitations -> BASE-01/02 and E-M4-001.
- Section 5: pipeline identification/cache effectiveness/selective preparation -> CACHE-01, PIPE-01, M2/M5 and BUG-01.
- Section 6: independent pacing irregularities and limiter comparison -> BUG-02/M4.
- Section 7: actual GPU timing, translation profiling and submission -> PROF-01, GPU-01, M3/M6/M8.
- Section 8: swapchain/LiveContainer sizing -> BUG-03/M6.
- Section 9: Balanced/Adaptive validation -> WORK-01/02 and M7.
- Section 10: visual requests and MetalFX limits -> GAP-03, RES-01, UPSCALE-01/M9.
- Section 11: compatibility warnings -> COMPAT-01.
- Sections 12–16: priorities, benchmarking, acceptance and preservation -> master milestones/test protocol.
- Section 17: lightweight monitoring, export, real power/GPU/temperature and overhead -> M1/M3.
- Section 18: principal energy objective and separate device profiles -> M10 and standing instructions.
- Section 19: fixed/dynamic resolution independent of MetalFX, encoding/state/resource/command-pool work, buffering/synchronisation, JNI/Bionic/futex and version benchmarking -> M8/M9. Three swapchain images are already observed; triple buffering is not an unimplemented feature.
- New device summary: E-M4-002; increases diagnostic priority without proving regression or savings.

## Record future outcomes

Append decision date, roadmap/experiment IDs, evidence references, build/device/conditions, result (positive, inconclusive, no benefit or regression), retained/reverted setting and reopening trigger. Do not delete unsuccessful work or turn historical priority scores into measured predictions.

2026-10-25: Approved permanent-plan structure saved as documentation only. Next action is the lightweight measurement implementation audit; no behavioural optimisation, energy validation or iPhone validation completed by this task.

2026-10-25 — M1 implementation: reuse Vulkan host counters and selected existing event logs; no raw per-frame file logging or GPU waits. Bounded histogram percentiles are explicitly estimated (0.1 ms upper bins; overflow conservative worst). Multi-second hitches are retained, unlike older cadence logging that discards long gaps. Keep diagnostics default off and measure overhead before adoption. M0 -> M1 -> M2/M3 is the next evidence sequence. No optimisation benefit is verified by these coding checks.

2026-10-25 — E-M4-003 / M1 data audit: first generated report at selected 2128 × 1600/Balanced is explicitly unplugged. Retained host cadence 55.42 FPS, worst interval 587.229 ms, 69 slow pipeline calls (worst 312.790 ms), 6 native drops and zero coarse battery estimate need JSON context. Preserve the baseline. Inspect existing files before requesting another run or claiming regression/efficiency; no timing causality from unrelated maxima and no zero-power conclusion. M1 remains open, enabling M2/M3 once evidence quality is understood. No runtime settings changed by this evidence update.

E-M4-003 log supplement: creation explains some closely corresponding hitches but not the approximately 587 ms event whose window records only a 0.317 ms creation call. Maintain parallel M2 and M3/M4 paths after M1 telemetry audit. Actual resolution, applied Balanced QoS, nominal thermal classification and cache persistence are supported by the pasted text; none proves energy efficiency. Do not treat guest BatteryReceiver stubs as proof of failed native battery telemetry.

2026-10-25 — Broad authorised iteration: M1 now separates render observation from reporting locks, reports actual loss categories/coverage, labels flat battery readings unresolved, and tags events with plan IDs/subsystem/outcome plus record/occurrence time. M2 identification is intentionally partial and opt-in; it cannot replay or prewarm complete pipelines. Cache feedback is passive and unavailable unless a valid guest chain exists. M4 engine-only experiment is default off and preserves engine/FIFO/thermal safeguards. M3 source investigation confirms the prebuilt interface does not expose completed Metal buffers; M9 adds capability detection only. MetalFX spatial prototype can advance after actual GPU evidence and safe interop design, without waiting for every scheduling/driver experiment. No energy/performance benefit has been verified by these implementations.
