# NATIVE-BATCH-5 benefit review and ten-point conditional target

User asks for at least10 potential fixed-roadmap points and an end-to-end code review supporting benefit. This request does not authorise fabricated evidence or changed weights. Scope is the Dungeons execution path and affected components, not a claim that every line of all engines, third-party libraries and generated code has been audited.

Sequence: E-M4-007 rules out host-limiter removal as a demonstrated fix -> review settings/launch/Vulkan/cache/Metal/presentation/worker/collector lifetimes -> complete M5 persistence/preparation candidate and independent feedback correction -> required Apple checks/IPA -> targeted physical attribution and net-benefit acceptance. The narrower preparation capability test remains first; no bulk test assignment.

## Fixed conditional coverage

[NATIVE-TEN-v1 scenario](progress/native-ten-v1.scenario.json), [immutable definition-time projection](progress/native-ten-v1.projection.json), unchanged HUSK-ROADMAP-v1/whole-milestones-1.

| Existing gates | Potential additional points | Evidence still needed |
| --- | ---: | --- |
| M5-I1/I2/I3 |2.40| Native ownership/serialization/concurrency tests, pinned driver/app/IPA success |
| M5-D1/D2/D3 |2.40| Matched same-event first/repeat/restart, correctness/lifecycle/cache, separate loading/preparation/gameplay work |
| M5-E1/E2 |3.20| Representative severe stalls reduced and loading-plus-gameplay net energy cost acceptable |
| M3-D2 |1.35| Representative CPU/GPU/presentation attribution with coverage/exclusions, including sampled role/explicit Mach identity where available |
| M6-D3 |0.70| Aspect/input/latency/lifecycle/buffering regressions excluded on the tested path |
| **Total ten existing gates** |**10.05**| **All must actually pass; current progress is unchanged while pending** |

At definition26.27% -> conditional36.32%. If required Apple validation first earns2.40points, actual would become28.67% and the remaining7.65points would still need device/benefit evidence. This is not the historical VALIDATE-50-v1 target, not an energy-saving percentage, and not a guarantee results will be positive. The old50.17% definition-time scenario remains separately retained. No weaker gate, reweighting, assumed equipment or absent future Duo is hidden in this arithmetic.

## End-to-end review findings

| Path reviewed | Mechanism / risk assessment | Verification / consequence |
| --- | --- | --- |
| AppWindows -> TLAppSettings -> TLUnityView -> native entry | Each new option defaultOFF, persisted/forwarded independently; same experimental driver in native modes1/2, original driver when native and spatial bothOFF | Correct misleading UI text that MetalFXOFF alone necessarily restores the original driver; full restart required; build and on-device launch/config check |
| Vulkan pipeline wrapper -> persistent Vulkan store | Existing store synchronises metadata/checkpoint access; historical store-lock wait0 means no evidence it dominates shader hitches. Cache seed accepted does not mean reuse | Preserve existing compatible cache/checkpoint implementation; no speculative lock rewrite or cache-size claim |
| Pinned MVKPipeline -> Metal compiler/archive | Original pinned compiler lacks native binary archive attachment. New path attaches an immutable archive to complete owned native descriptors; defaultOFF forwards original call directly | Real native-component tests and exact source anchors; compilation fallback once; first-ever/MSL-library work remains; actual archive benefit still unknown |
| Capture -> explicit pause -> native preparation -> disk -> restart | Capture only successful slow calls, retain<=8 complete Metal descriptors. Explicit preparation owns native objects across teardown, publishes by generation, serialises under a nonblocking directory lock and bounds owned files | Test caller release/async completion, failure/oversize/corrupt data/pruning/teardown. Successful write must not be falsely called failed if teardown prevents publication. Full first/repeat/restart test and preparation receipt required |
| Preparation accounting -> export -> offline audit | Work moves out of gameplay but can still consume CPU/energy. Receipt includes host wall/process CPU, preceding session/device/build, exact driver manifest, config and monotonic endpoints | Reject mismatched build/device/session/driver/config, invalid counts/size/time, unsuccessful write and missing restart restore/attachment. Never infer archive hits/watts from these checks |
| Vulkan present -> clock adapter -> native feedback | E-M4-007 native20.83ms tail persists with host sleep0. Guest feedback clock mismatch is a distinct API defect; actual MoltenVK feedback can contain estimates | Independent feedback-only correction preserves immediate scheduling; timed mode remains separate. No automatic engine-only adoption,48Hz diagnosis, new history polling or claim display timing is authoritative |
| Queue submit -> Metal drawable/encoding/completion | Native drawable acquisition can occur inside encoding; short vkAcquire does not exclude drawable back-pressure. Submit wall substantially exceeds caller CPU in E-M4-007 | Existing bounded GPU sampler classifies final known labels; unknown remains unknown. Keep CPU encoding, GPU time, callback latency, drawable wait separate; deeper traces still required |
| Worker policy -> CPU samples -> joins | Ordinary normal workers account for only~3% of matched-thread CPU in E-M4-007; core placement and energy share unknown. Synthetic policy IDs cannot safely join Mach thread IDs | Add explicit Mach identity on rare policy observations, preserve all QoS/rollback/fast-worker safeguards. No forced E-core policy, guessed unnamed-thread role or claim strict Adaptive has benefited energy |
| Graphics V4 -> selected resolution -> optional spatial path | Original output/quality controls remain. MetalFX already has actual lower-input/higher-output texture evidence, but internal scene quality and net cost are incomplete | No silent resolution change, automatic dynamic resolution, temporal implementation or driver-version upgrade; retain separate existing M9 controls and original rollback |
| Routine monitoring -> battery/report tools | Per-frame disk logs and automatic heavy profiling would add work. Short one-step drain extrapolation is misleading; CPU time and nominal thermal status are not watts/degrees | Existing bounded collection/budgets unchanged, new preparation I/O explicit/paused, conservative human battery policy with raw arithmetic retained, monitoring overhead still a physical gate |
| Bionic/JNI/synchronisation | Existing completed-once/futex fixes have source/tests and synthetic evidence, not representative heat attribution. Missing JNI warnings alone do not prove meaningful cost | No unrelated compatibility rewrite or automatic priority change; keep trace-guided M8 questions open |

Review establishes plausible mechanisms and guards, not a guarantee of lower sustained heat. Native archive attachment adds descriptor/counter work when enabled and reading/serialising/preparing costs time. That can outweigh savings. Reject or keep itOFF if matched measurements show no useful stall/net-cost benefit; retain negative results. Power/temperature and monitor-off captures require verified supported external workflow/equipment. Charging, display brightness/content and ambient conditions must be controlled separately.

## Reproducible analysis, without a new installation

```sh
python3 scripts/audit_native_preparation.py first-use-diagnostics.json preparation-receipt.json restarted-diagnostics.json --output preparation-audit.json
python3 scripts/compare_efficiency.py driver-only-diagnostics.json archive-enabled-diagnostics.json --recipe native-archive --output archive-comparison.json
python3 scripts/roadmap_progress.py docs/performance/progress/roadmap-v1.json --scenario docs/performance/progress/native-ten-v1.scenario.json --output conditional-native-ten.json
```

The receipt audit hashes original/decoded inputs, refuses evidence-file overwrite and reports distinct first-use/restarted metrics without treating their different cache states as a controlled comparison. CPU may exceed wall across multiple threads and excludes compiler/system processes. Preparation wall may exceed2seconds because the budget only limits new call starts. Matching identity/bytes/attachments is preflight evidence, never an automatic gate pass or cache hit. The controlled recipe instead uses mode1vs2 with identical driver manifest and actual mode2 restore/attachment, matched route/duration/cache/brightness/charging and other controls fixed. Feedback-only recipes require actual independent runtime treatment, observations and no clock/unsupported-chain error. All electrical/temperature fields remain unavailable without real data.


Pinned queue-label audit: MVKQueue.mm lines166–200 constructs command buffers, applies per-command-use labels after creation and caches the labels for BeginCommandBuffer/QueueSubmit/QueuePresent/AcquireNextImage. Sampling reads labels on completion, after this assignment, rather than at the factory interception point. Original debug labels can replace them; unknown/other remains explicit instead of guessing a role. [Exact upstream source](https://github.com/KhronosGroup/MoltenVK/blob/db66022459ffb663aa2b50f6b018bc2e124f5edf/MoltenVK/MoltenVK/GPUObjects/MVKQueue.mm#L166). Labels are attribution hints, not proof of exclusive per-frame GPU work or system energy.
