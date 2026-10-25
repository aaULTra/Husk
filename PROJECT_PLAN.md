# Husk master development plan

Updated: 2026-10-25. Status: 104-check diagnostics candidate built; UI-01 overlay-clearance correction pending Apple build/device verification; benefit/overhead gates open.
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
| PIPE-01 | Pipeline identification | Partial implementation: opt-in shader/state group signatures, bounded occurrences/slow events and passive valid feedback; existing timing retained | Device first/repeat/restart comparison pending; complete state identity absent | No prewarming key or verified energy benefit; see docs/performance/11-pipeline-identification.md |
| WORK-01 | Balanced policy | Implemented, default; critical roles preserved | Active in supplied runs | Energy benefit unmeasured; baseline comparator |
| WORK-02 | Adaptive Trial | Implemented revised cheap-pipeline admission and self-applied caps/rollback | Real-device admission/application fix not independently verified here | NOT COMPLETE: energy A/B versus Balanced pending |
| SUBMIT-01 | Async submission option | Implemented, experimental; Driver Default retained | No controlled benefit evidence | Pending independent A/B |
| PROF-01 | Detailed MoltenVK profiling | Implemented; strict 1.4.2/private API 43, 1152-byte guard, optional/off | Earlier report contains driver activity data | Adds overhead; no genuine GPU/power measurement |
| MEAS-01 | Efficiency Test sessions/export | Implementation candidate: bounded aggregation, exclusions, process/API sampling, Markdown/JSON export | Previous build passed 92 checks; schema-v2 ring/loss/reporting/plan tags now implemented with portable tests; final 104-check Apple build passed; device coverage/overhead checks pending | M1 remains open; monitoring overhead and energy unmeasured |
| GPU-01 | Genuine GPU execution timing | Source investigation: callback latency is not GPU time; completed buffers not exposed by current interface | Measurement gap | Instruments or safe completed-buffer access |
| UPSCALE-01 | MetalFX spatial upscaling | Capability query added to session metadata; upscaling itself is research, not wired into presenter | None | Separate prototype only after GPU evidence |
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
| GAP-04 | E-M4-003 JSON archived and audited; pasted attempt log available; earlier run raw logs still unavailable | Use current JSON audit; preserve provenance and earlier gaps |
| MON-01 | Schema-v1 loss defect confirmed; schema-v2 bounded independent frame ring and loss categories implemented/tested | M1: Apple build then real-device coverage/overhead acceptance remains open |
| MON-02 | Schema-v2 null/unresolved flat-battery reporting implemented with sample count/span/change; API freshness still unknown | M1: verify against system battery indicator; no watts or efficiency claim |
| UI-01 | User screenshot: native game toolbar overlaps visible iPadOS/LiveContainer status controls at top left/right | UI overlay clearance correction implemented; Apple build and physical screenshot/gesture/lifecycle verification pending |
| COMPAT-01 | isnan/JNI/optional OBB/ANGLE warnings not demonstrated performance causes | Investigate only with malfunction or traceable cost |

## 6. Next actions and task handover

Current engineering task: M1 measurement foundation. Source/lifecycle/UI audit completed; observer and export candidate implemented without optimisation toggles. Apple build/package validation passed; complete physical-device correctness and overhead checks before M1 acceptance. M2 then extends existing slow-call support instead of duplicating it. Obtain M4 baseline evidence with monitoring overhead separated, then prioritise measured costs.

Physical iPad tasks: export raw first/repeat/restart logs; validate lightweight reports; run matched monitoring-off/on baseline; gather unplugged power if tooling supports it and surface/ambient temperatures; later perform limiter, submission and Adaptive A/B separately.

2026-10-25: User approved the structured plan and authorised saving it to GitHub. M0 documents prepared from the targeted repository inspection and supplied Sections 1–19/new-run summary. No runtime source, defaults, cache files or graphics settings changed. No device tests performed. M1–M10 remain open; all energy claims pending.

At each handover append dated implementation/evidence/decision updates here and in the linked records. Do not close a milestone whose physical-device gate is pending.

### 2026-10-25 — M1 / MEAS-01 implementation candidate

Sequence: M0 durable instructions -> M1 measurement foundation (current) -> M2 variant/cache identification -> M3 GPU/power baseline -> separately measured optimisation experiments. Every future task/update must explain its relationship to this sequence, per the user's standing instruction.

Candidate adds a default-off Efficiency Test panel in UE4 Game Graphics and the fullscreen game bar; CPU samples at roughly 2 seconds, memory at 10 seconds, battery at 30 seconds/on changes, environment transitions, selected existing cache/worker/pipeline log events, host Vulkan statistics and bounded 0.1 ms histogram summaries. Stop/export writes Markdown and schema-v1 JSON in Documents/EfficiencyTests; nothing is transmitted automatically. Metadata captures actual launch arguments and packaged build identity; packaging now stamps the full source SHA.

New files: efficiency C header/core, Swift diagnostics UI/model and Foundation-only calculation helpers; integration touches the bridge, settings, native view, existing Vulkan observation points and selected log capture. Portable observer/math tests are wired into the IPA workflow. Rendering, resolution V4, limiter algorithm, worker policy, submission defaults and cache contents/lifetimes remain unchanged.

Validation so far: 82 existing required portable checks + 8 observer tests pass on Linux. Swift calculation/JSON check is skipped locally because swiftc is unavailable; macOS CI is required. Broad test discovery additionally encountered an unrelated scanner test requiring unavailable clang; this does not replace the successful named required suites. iOS build/package and physical-device checks remain pending at this entry.

Limitations: session is in memory until exported; retained windows/samples/events are bounded with explicit drop counts. Host cadence currently comes from the Sharp Vulkan path. Percentiles are estimated histogram bounds; long hitches are retained. API calls crossing exclusion boundaries are classified by completion time, not split. Peak footprint, actual GPU execution, actual displayed frames and verified cache hits are unavailable. Driver-phase details remain in the separate attempt log. Power and numerical temperature require external tools. No energy/heat reduction or negligible-overhead claim is made.

Next: validate CI then use the device checklist in docs/performance/10-lightweight-monitoring.md. Keep M1 open until correctness and overhead A/B are established. Adaptive Trial energy validation and M2–M10 remain pending.

M1 CI update: [run 40162915034](https://github.com/aaULTra/Husk/actions/runs/40162915034) passed regression checks, Swift CPU/battery/JSON checks, iOS compilation and IPA packaging at 2f01d6de94d3bdf14adf3df2c30b4bdd31eea451. Final review adds an actual-wrapper monitoring-on forwarding/no-extra-sleep check, disables export before a stopped report exists, and preserves the packaging script executable mode. The follow-up candidate must pass its own build. These are M1 validation refinements; M2/M3 remain next, with physical overhead/energy checks pending.

### M1 final build evidence and next gate

[Run 40163119357](https://github.com/aaULTra/Husk/actions/runs/40163119357) passed **92 checks**, iOS compilation and validated IPA packaging at source commit `1a68f40a377be7a8d0feac1bf05b6170d87659b9`. [Installable artifact](https://github.com/aaULTra/Husk/actions/runs/40163119357/artifacts/12586749378) is named Husk-LiveContainer-IPA; archive digest `sha256:9026ce4fce4bd70758d986d760fef0081367a13b090c1b5e49e75df8a294018d`. Artifacts expire; retain the build/source identity with any downloaded copy.

Packaged identity is `1a68f40a377be7a8d0feac1bf05b6170d87659b9-dirty`: the existing staging recipe rewrites project.yml to use checksum-pinned release libraries/resources and XcodeGen regenerates the project. The suffix is retained honestly, not silently removed. No on-device result is inferred from successful packaging.

Sequence: M0 complete -> M1 coding/build validation achieved, device correctness and monitoring-overhead gate OPEN -> M2 stable pipeline identity/cache-reuse diagnostics -> M3 actual GPU, power and external temperature baseline -> independently justified optimisation trials. M1 does not establish an energy benefit. Adaptive Trial admission/application/energy validation, BUG-01/02/03, MetalFX and every later investigation remain unresolved.

Immediate user-device action: follow docs/performance/10-lightweight-monitoring.md at reference settings; export report.md + diagnostics.json and the raw attempt log. Immediate next engineering action: M2 audit/implementation, reusing the M1 foundation without introducing prewarming or changing rendering defaults.

### M1 / E-M4-003 — first user-device report, unplugged

[Evidence record](docs/performance/runs/E-M4-003.md): user confirms Balanced/2128 and unplugged. Build 1a68f40-dirty on iPad16,5 / OS 27.2 exported 405.467942 s, 55.421611 FPS host cadence, p50/p95/p99 16.7/20.9/21.1 ms, maximum 587.229 ms, 69 slow pipeline calls (worst 312.790 ms), 6 collector / 0 export drops and 0.0 estimated battery pp/hour. Configuration is launch metadata; actual swapchain/internal resolution and applied worker QoS need supporting data. CPU/memory/thermal samples and included duration are not present in the pasted report.

Sequence: M0 -> **M1 data audit now** -> M2 pipeline identity/cache reuse -> M3 true GPU/power/temperature -> targeted optimisation. M1 has a user-device-generated summary, but collection coverage, zero-drain interpretation, lifecycle/exclusion correctness and monitoring overhead are not verified. Native drops are not categorised; cadence gaps may be reset after contention. Do not attribute the worst interval to the worst pipeline call without timestamps, infer zero power from a zero battery estimate, or compare these aggregates directly with older logs whose sampling/gap policies differ.

Immediate next action: obtain diagnostics.json and full attempt log from this exact test. Inspect windows/exclusions/interval count and duration, sizes, CPU/memory/thermal, pipeline/event correlation and battery states/levels/valid observed seconds. If a measurement defect is demonstrated, fix it within M1 before a new baseline. Then perform matched monitoring-off/on checks. M2 remains the next engineering investigation; do not change resolution, scheduling, submission or prewarm pipelines on this summary alone. All later work including Adaptive energy validation stays open.

E-M4-003 accompanying-log update: actual 2128 × 1600 swapchain/drawable survives resume; Balanced QoS application is logged; Driver Default reads synchronous=1/prefill=0/limit=64. Cache acceptance 11,580,626 bytes and later save 12,266,295 bytes are confirmed mechanisms, not cache-hit evidence. Shown thermal classifications remain nominal. The 245.04 ms interval and 243.308 ms pipeline call strengthen BUG-01/M2; the 587.23 ms interval with only 0.317 ms of pipeline creation and the repeated approximately 20.9 ms p95 cheap/no-pipeline windows strengthen BUG-02 and M3/M4. Retain both investigations; no single shader-stall explanation covers this run. A legacy 636.38 ms interval is lifecycle-adjacent and needs exclusion context. JSON remains the immediate M1 dependency, including native battery and drop interpretation. No runtime changes in this evidence task.

### E-M4-003 JSON received — M1 evidence-quality audit

[Detailed audit](docs/performance/runs/E-M4-003-JSON-audit.md), [archived original JSON](docs/performance/runs/E-M4-003.diagnostics.json). All checked summary/window aggregates reconcile: 21,350 retained intervals over 385.228790 s, 55.421611 FPS, 69 slow pipeline calls, maximum 587.229 ms; 37 windows / 204 samples / 71 events. Three exclusions total 16.537365 s. Session includes startup and has no explicit mission marker.

Battery: 15 unplugged readings all approximately 70%; valid estimator span 309.853644 s. Zero estimate is explained, not an energy saving. Brightness 100%, thermal classification nominal, LPM off; 120 Hz is maximum capability, not observed display timing. Weighted process CPU activity approximately 63.049% of one logical CPU; maximum observed footprint 3.592244 GiB, with later approximately 3.55 GiB plateau. GPU execution, electrical power and physical temperature remain unavailable/external.

Source audit confirms MON-01: a contended host/event observation can reset the next frame anchor. The six mixed-category drops mean retained maxima/cadence cannot establish complete coverage. Long pipeline calls in windows with short retained frame maxima may be off-critical-path or incompletely observed. JSON supplies the 312.790 ms call and 69 total slow calls absent from the legacy per-window detail. The 587.229 ms event remains separate from long compilation: its JSON window maximum pipeline call is 11.567 ms (legacy windows differ).

Updated sequence: M0 -> **M1 targeted cadence-loss/battery-reporting refinements and tests now** -> M1 device coverage/overhead acceptance -> M2 stable variant/cache feedback -> M3 true GPU/power and M4 independent limiter comparison -> measured optimisation trials. Do not request another broad run before addressing known collection limits; no new user files are currently required for this audit. Retain existing graphics, Balanced and Driver Default. Adaptive energy validation and all later research remain open. This commit is evidence/documentation plus the original data only, with no app code/settings changes.

### M1 / MON-01 / MON-02 refinement candidate

Sequence: E-M4-003 audit -> M1 observation integrity/reporting patch -> M2 pipeline identity -> M3/M4 execution/pacing experiments. Frame observations now enqueue into an 8,192-slot bounded ring independently of host/event reporting locks; aggregation moves off the present path. Host/event contention no longer clears cadence anchors. Actual frame enqueue loss is counted separately with lost interval duration/maximum, and distribution completeness is explicit. No claim of complete coverage follows when frame drops occur.

Schema v2 retains old fields and adds separate loss categories, battery status/count/span/observed level change, CPU/footprint/thermal context in Markdown, phase markers and tagged event plan IDs/subsystem/outcome. Unchanged battery samples yield an unresolved status and null drain rate, not zero energy. Event record time and available occurrence time are separate; API success never marks benefit validation complete. Stop drains final buffered events.

Portable tests cover long hitches despite host/event contention, true frame loss, overflow, stale-session rejection, exclusions and reconciliation. Swift tests add unchanged/increasing battery status and plan/event-time classification. Apple build and real-device overhead/coverage acceptance remain pending. Defaults, V4, Balanced, cache and limiter behaviour are unchanged.

### M2 / PIPE-01 diagnostic candidate

Depends on M1 collection integrity. Added opt-in Pipeline Identification (Diagnostic), forwarded through fullscreen/window launch paths and off by default. Shader SPIR-V is fingerprinted once at module creation; bounded module metadata is invalidated on module/device teardown. Creation requests receive deterministic **partial shader/state group signatures**, using stages/entry points/specialization values, flags/subpass and selected assembly state, without hashing pointers, handles or padding. Fixed-state/layout/render-pass coverage is incomplete: these are not full variant keys and cannot support replay/prewarming. M2 remains partial.

Bounded first/second-group and slow-call events record original call/batch size, up to four signatures, host elapsed/completion time, cache presence, result and passive first-pipeline creation feedback if a valid guest-supplied feedback chain exists. No extension/feedback chain or compilation flag is injected. Unsupported/absent feedback remains unavailable; a valid no-application-hit flag is not proof that all compilation was required. Repeated partial groups do not prove exact pipeline reuse. Diagnostic metadata/logging adds overhead and needs dedicated short tests.

Tests exercise stable signatures despite handle changes, differing entry/subpass/topology/specialization, teardown invalidation, off-path safety, valid feedback versus mere cache presence and bounded events. Device first/repeat/restart correlation and actual feedback availability remain open. No cache behaviour, compilation order or asynchronous prewarming changed.

### M4 candidate and M3/M9 feasibility progress

M4: added default-off engine-only 60 FPS host-limiter comparison, saved/backward-compatible and forwarded through fullscreen/window launch paths. Engine t.MaxFPS and FIFO are retained; native 30/20 serious/critical thermal caps and the selected 30 FPS mode remain protected. Pure-policy and actual-present-wrapper tests cover defaults, host-sleep bypass and thermal/30 FPS preservation. No pacing/energy benefit is verified.

M3/M9: inspected MoltenVK 1.4.2 queue/statistics sources; existing callback metric is confirmed host commit-to-callback latency, not GPU execution. Current prebuilt driver interface does not expose its completed Metal command buffers. Documented Instruments/driver-instrumentation alternatives and lifetime/overhead requirements. Efficiency Test metadata now queries actual Metal device and supported MetalFX spatial capability without adding rendering work or claiming integration. See docs/performance/12-gpu-metalfx-and-limiter.md.

MetalFX spatial implementation remains M9 research. It may proceed after a trustworthy M3 GPU baseline and safe interop design, without waiting for every later research item. No upscaler, dynamic resolution, driver upgrade, worker-policy change or prewarming is part of this candidate. M4/M6/M7 still require independent A/B tests; user authorisation to progress broadly does not establish measured benefit.

M6 observation follow-up: existing swapchain-boundary main-thread sizing logs now include view bounds in points, drawable dimensions in pixels and affine transform components, tagged M6/BUG-03. No size, transform, compositing, buffering or presentation settings are changed. This extends the existing instrumentation; overhead/cost of suboptimal presentation remains unmeasured.

Current validation sequence: 103 required portable checks pass locally; the single Swift calculation/export executable check is skipped on Linux and is required in macOS CI (104 checks total there). Three logical implementation commits isolate M1, M2 and M4/M3/M9, with M6 observational follow-up. New options default off and cached launch settings remain compatible. Run the complete Apple build/package before calling this a device candidate.

Next device sequence after build: corrected M1 baseline with identification/limiter experiments off -> separate short M2 identification session -> separate M4 dual/engine-only comparison -> M3 execution/power trace -> M6 async and M7 Adaptive A/B when repeatable. Keep brightness and environment matched; no lowering resolution/quality to manufacture gains. Outstanding bugs, GPU/energy gaps, full variant identity and all untested experiments remain open.

Apple validation: run 40167973725 at ed806f3 passed all 103 checks including Swift math/event/export tests, but iOS compilation caught memberwise argument ordering in the fullscreen/window Swift views. Corrected the stored-property ordering to match existing explicit launch arguments; rerun of full build/package is required. This build failure is retained as validation history, not device evidence.

### M3/M7/M8/M9 CyPort source audit and M8 yield observation

Located and inspected public Thijs2004/CyPort at main SHA 65e2e57a95263f60516f567e274780d8ebd97072. [Source comparison](docs/performance/13-cyport-source-review.md) separates transferable mechanisms from Cyberpunk-specific implementation/claims. Relevant paths: QoS grouping (already represented by guarded M7), yield backoff (needs M8 cost evidence), actual GPUStartTime/GPUEndTime sampling via Metal commit interception (new M3 research alternative requiring safe LiveContainer scope), and native-game MetalFX integration (not present in Husk). No claims of core placement or reproduced cooling benefit are accepted from comments alone.

M8 observation implemented: clock-free included-span guest sched_yield counters in import/syscall paths, exported as cumulative metrics with plan association. No backoff, priority change, thread suspension or extra sleep is applied. This establishes whether yield activity deserves deeper CPU tracing; it is not proof of wasted energy. Added enabled/excluded/off counter test. CPU/GPU energy, Adaptive benefit and MetalFX remain unverified.

Intermediate corrected Apple run 40178005735 passed all 103 then-current checks, iOS compilation and IPA packaging at a41c030575fad6ed7ac7353b1177fbae0e57ca12. The small M8 observation addition now requires a new final build (104 checks); do not confuse the earlier artifact with the final candidate.

### Final candidate / validation handover

Source `6c4fef3d20178f8b4a49a157a5863b2de981a616`, packaged identity with `-dirty` from documented staging/XcodeGen. [Run 40178749888](https://github.com/aaULTra/Husk/actions/runs/40178749888) passed **104 checks**, iOS compilation and validated IPA packaging. [Final IPA artifact](https://github.com/aaULTra/Husk/actions/runs/40178749888/artifacts/12593800140), archive digest `sha256:ebc30a6ea14e8be300296e796cdee635cebc854bcf69d8d3f717e548146b0ec5`. The intermediate a41c030 artifact omits M8 yield observation; use this final source for the next test. Documentation-only follow-up does not change the binary.

Implementation progress: M1 cadence ring/loss categories, honest battery status, phase markers, CPU/memory/thermal report context and plan-tagged logs; M2 opt-in partial shader/state signatures and passive feedback; M4 default-off engine-only comparison preserving thermal/30 FPS caps; M6 point/pixel/transform observation; M8 included guest-yield counts; M3/M9 actual-source feasibility work and MetalFX capability metadata. All runtime changes are reversible diagnostics or monitoring corrections. No default quality/resolution, worker policy, cache lifetime/format, submission mode, prewarming or upscaling behaviour changed.

Next physical sequence: install final IPA preserving data/cache; fully restart; retain 2128 × 1600, Sharp / Efficient, 60 FPS, Balanced, Driver Default, LPM off; Pipeline Identification OFF, Engine-only Limiter OFF and Detailed Driver Profiling OFF. Collect corrected M1 baseline with explicit phase markers and matched brightness/conditions. Export schema-v2 report + JSON; compare native battery levels with the system indicator. Confirm frame loss categories, exclusions, lifecycle and cache behaviour, then quantify monitoring-off/on overhead.

After M1 evidence: dedicated M2 first/repeat/restart test with identification ON and other experiments OFF; dedicated M4 dual/engine-only A/B with identification/profiling OFF. M3: choose accessible Instruments trace or design scoped GPU buffer sampling using the reviewed CyPort mechanism; current monitor still cannot claim GPU execution/power. M7 Adaptive benefit and M6 async require their own controlled tests. M9 spatial prototype can be the next separate rendering feature after trustworthy GPU evidence and a safe interop design, ahead of lower-value research if justified. MetalFX support capability alone is not implementation or benefit.

Do not mark M1 device acceptance, M2 full identification/cache efficacy, M3 GPU/power or any energy-saving optimisation complete from these checks. Existing failed/inconclusive experiments and both pipeline/non-pipeline bugs remain tracked.

### UI-01 / M1 / M6 — hosted status/tool bar overlap

User screenshot shows Husk controls and iPadOS status items occupying the same top row. Existing .statusBarHidden(true) / persistent overlay preferences are not sufficient for the observed hosted state. Candidate adds an event-driven reader of the actual attached window's safe area/status frame, converted to overlay-local coordinates. Extra top/side clearance applies only to Husk's toolbar/log overlay. A 52-point window-top reserve (status plus host window-control row) covers the LiveContainer iPad case where guest APIs claim hidden/zero-inset status chrome. Already-safe layouts avoid double padding; rotated/notched geometry uses current insets. No polling, global window selection, private API or status-bar forcing is added.

Sequence: UI-01 usability/lifecycle correction supports M1 diagnostic access and M6 sizing correctness; it does not replace the ongoing M1 test or any M2–M9 experiment. The native game view, selected launch size, swapchain, graphics, FPS, worker policy and telemetry are untouched. User may finish the currently installed 6c4fef3 test before upgrading; associate its results with that source SHA.

Validation: Foundation geometry cases cover hosted zero-inset fallback, visible status area, already-inset/no-double-padding, standalone hidden status, side safe areas, floating placement, empty geometry and converted scaled coordinates. Swift checks and clean iOS build/package are required. Actual iPad/LiveContainer screenshot acceptance remains pending: show/hide toolbar, open/close diagnostics, invoke/dismiss Control/Notification Center, resume and supported window/rotation transitions; verify no persistent overlap, clickable controls and retained 2128 × 1600 output/input/audio. System panels retain their standard ability to cover the app while open. No performance or energy claim.

UI-01 validation history: first run 40180376426 stopped in the new macOS geometry check because its standalone helper needed an explicit CoreGraphics import. Added that import to helper and test; no layout policy or rendering change. Re-run the full checks/build/package before distributing this correction.

UI-01 follow-up screenshot: user also identifies the top-left hosted window/ellipsis control covering the game area. Extend fallback clearance to include the host window-control row (52 window points total before local-coordinate conversion). Husk controls move below that reserved region; LiveContainer/iPadOS retains ownership of its own buttons. This does not remove host buttons from the game picture or resize the render surface. User screenshot verification after the next build is still required.

### E-M4-004 — new gameplay files and subjective warmth

[Audited record](docs/performance/runs/E-M4-004.md), original report and JSON archived. Source 6c4fef3-dirty (prior to UI fixes), same 2128 × 1600/Balanced/Driver Default/60 target and all new experiments OFF. 736.427458 s wall, 41,659 retained intervals / 728.651882 s, 57.172706 FPS, p95/p99 20.9/21.0 ms, maximum 474.380 ms, 40 slow pipeline calls (maximum 254.135 ms). All checked summary/window aggregates reconcile. Frame/host/event losses 0/1/0: this supports corrected M1 loss separation in this run; overhead and actual display timing remain open.

Battery is unplugged, with one five-point reported change (50% ->45%) and approximately 27.5 pp/hour over 653.994401 estimator seconds; this is coarse, not watts or reliable small-difference evidence. Brightness 100%, nominal thermal classifications; user says warmer than not playing. Weighted process CPU approximately 62.81% of one logical CPU, footprint maximum observed approximately 3.476 GiB. Yield count 4,076 (~5.59/s retained cadence duration) does not establish dominant spin waste. MetalFX spatial support true is now actual device capability evidence, not an upscaling implementation.

Pipeline-associated events (255.822/254.135 ms frame/call) and separate non-pipeline stalls (474.380 ms with pipeline maximum 1.697 ms) persist. Continue M2 and M3/M4 independently. Finish UI-01 and monitoring-overhead acceptance, then run separate identification and limiter tests; no combined behaviour changes or default resolution cut. User's current test remains associated with 6c4fef3.
