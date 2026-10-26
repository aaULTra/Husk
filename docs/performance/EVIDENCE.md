# Husk performance evidence register

Updated: 2026-10-25. Source of priorities: [PROJECT_PLAN.md](../../PROJECT_PLAN.md).

## Provenance and limitations

E-M4-001 and E-M4-002 are user-supplied report summaries from the project transfer, not independently parsed raw logs. Values are reported observations, not new measurements by Codex. Their temporal correspondence is suggestive, not exclusive causal proof. Attach complete raw exports and checksums/build identity when available; keep these original entries intact.

Metric provenance: MEASURED = directly observed by a named collector; ESTIMATED = calculated with stated inputs; UNAVAILABLE = no valid collection; EXTERNAL = Instruments or physical equipment. A reported measurement still needs a source-quality label. Neither run establishes electrical energy savings.

## E-M4-001: earlier extended high-resolution reference

Reported device: 13-inch M4 iPad Pro, 1TB/16GB; Dungeons V1.4. Analysed source SHA: 3c2d52c0f26ca9b40796633b169c40fd7f535e7c (exact installed binary identity not independently checked).
Configuration: 2128 × 1600 presentation, Sharp / Efficient, 60 FPS, Balanced, Driver Default, persistent cache. Detailed driver profiling present in the described run; LPM off. Do not use this profiled run as the uninstrumented energy baseline.

- More than 33,000 frame-progress events; many windows at 60 FPS.
- Example p95 intervals: 16.70–19.75 ms; these are host cadence, not authoritative displayed-frame timestamps.
- Highlighted hitch: 347.93 ms maximum frame interval and 343.701 ms graphics pipeline call.
- That window: 14 graphics pipeline calls, 1171.665 ms aggregate, five above 16.67 ms; cache argument non-null, store-lock wait 0.000 ms, success.
- Driver activity maxima in the same window: library compile 217.372 ms, library retrieval 223.974 ms, Metal pipeline compile 42.137 ms, SPIR-V-to-MSL 6.590 ms. Activities may overlap and must not be summed.
- Separate windows: approximately 33.58/33.80 ms maxima with zero pipeline calls.
- Cache restored 6,078,047 bytes; checkpoint 6,134,416 bytes.
- Reported thermal state nominal; reported jetsam headroom approximately 13.3–13.6 GB. This is not footprint.
- User observed smooth play and noticeable warmth while connected to charger; not excessive heat. No numerical temperature or power supplied.
- Deliberate late approximately 42 FPS slowdown was user-caused; exclude from normal-play conclusions while retaining surrounding diagnostics.
- Resolution retained through repeated resumes; three swapchain images reported. Internal scene target not independently established.

Conclusion: strong reported sustained-play and resolution-retention evidence, with severe first-use preparation and smaller independent irregularities. No measured energy optimum.

## E-M4-002: new reduced-presentation run

Received: 2026-10-25; actual session timestamp, binary SHA, duration, ambient temperature, brightness, starting temperature, charging state and exact gameplay/cache history not supplied.
Configuration: M4 iPad Pro 1TB, Dungeons V1.4, Sharp / Efficient, 1784 × 1336, 60 FPS, Balanced, Driver Default, persistent cache enabled. No detailed MoltenVK driver-phase output supplied.

- Stable sections still approximately 60 FPS.
- Worst individual graphics pipeline creation: 436.954 ms.
- One reported window: 39 slow pipeline calls and 6274.718 ms aggregate pipeline creation time. Window length and detailed category breakdown are unavailable; do not treat 39 as necessarily the total call count.
- Multiple frame stalls closely correspond to expensive pipeline calls.
- Other irregularities occur without pipeline creation.
- Cache restored 6,828,024 bytes; saved 9,692,442 bytes.
- Thermal classification remained nominal. Electrical energy and numerical temperature unavailable.

Conclusion: persistent-cache restoration has not eliminated expensive preparation. The log summary does not establish actual hits/misses or the driver subphase responsible.

## Comparison and permissible claims

| Metric | E-M4-001 | E-M4-002 |
| --- | --- | --- |
| Presentation dimensions | 2128 × 1600 | 1784 × 1336 |
| Pixel count | 3,404,800 | 2,383,424 |
| Stable cadence | Approximately 60 FPS | Approximately 60 FPS |
| Worst graphics creation | 343.701 ms | 436.954 ms |
| Highlighted window | 14 calls, 1171.665 ms aggregate | 39 slow calls, 6274.718 ms aggregate |
| Restored/saved bytes | 6,078,047 / 6,134,416 | 6,828,024 / 9,692,442 |
| Thermal classification | Nominal | Nominal |
| Energy comparison | Unavailable | Unavailable |

Pixel reduction = 1 − (1784 × 1336)/(2128 × 1600) = 29.9981203%, approximately 30%. This is an ESTIMATED arithmetic comparison of reported presentation dimensions, not a measurement of internal scene workload or power reduction.

Different scene, shader exposure, cache history, instrumentation and session conditions prevent a controlled regression or savings claim. Both runs strengthen the case for M1/M2 and separate BUG-02 investigation. The larger cache does not prove effective reuse.

## E-HIST-001: earlier observations retained

Initial Sharp output fell to 864 × 720; V2/V3 initially reached larger sizes but later fell to approximately 816 × 720. V4 established retention in later builds. Earlier larger-resolution trials included 41.6–57.4 FPS windows. These were not matched benchmarks.

An earlier attempt reported a roughly 590 ms hitch, restored approximately 4.96 MB and checkpointed approximately 5.38 MB. Comparing 590 ms with 347.93 ms does not establish a 41% improvement: different shader events may have occurred. Historical /100 engineering rankings are not measured percentages.

## Next evidence required

1. Complete source logs and binary SHA/configuration for each new session.
2. Stable variant identity and supported feedback for first use, same-run repeats and persisted-cache restart.
3. Unprofiled 2128 × 1600 reference with monitoring-off/on overhead comparison.
4. Genuine GPU timing, matched unplugged power and external temperature data.
5. Independent limiter, async and Adaptive versus Balanced experiments.

## New record template

ID/date/device; roadmap ID/objective; source/binary SHA; OS/driver; all graphics/limiter/worker/cache/profiler settings; scene/duration/environment; charging/brightness/starting temperature; collector and metric labels; raw artifact path/checksum; exclusions; distributions and repeat variability; correctness; energy result; interpretation limits; decision; next action.

## E-CI-M1-001: implementation/build validation, not device efficiency

2026-10-25, source `1a68f40a377be7a8d0feac1bf05b6170d87659b9`: [macOS run 40163119357](https://github.com/aaULTra/Husk/actions/runs/40163119357) passed 92 checks, iOS compilation and IPA packaging. Check counts by suite: graphics 17, resolution 6, source efficiency 6, thread policy 29, Vulkan timing 7, cache store 9, driver profile 9, observer 8, Swift CPU/battery/JSON 1. Observer tests cover threshold bins, long hitches, exclusions, window draining, disabled mode, bounded events, contention drops, clock discontinuities and size retention. The enabled-observer test exercises actual Vulkan wrappers without added sleeps or forwarding changes.

Artifact: [Husk-LiveContainer-IPA](https://github.com/aaULTra/Husk/actions/runs/40163119357/artifacts/12586749378), archive SHA256 `9026ce4fce4bd70758d986d760fef0081367a13b090c1b5e49e75df8a294018d`. Build metadata retains `-dirty` because staging/project regeneration modifies tracked build inputs; source SHA and workflow identify the recipe. Earlier candidate 2f01d6d also built successfully in run 40162915034; prefer the final candidate.

Evidence scope: coding correctness and build/package validation only. UIKit/Mach readings, panel lifecycle, actual exports on device, monitoring overhead, energy and physical temperature remain unverified. M1 stays open; this evidence enables device checks and M2/M3 work, not a performance/power claim. Existing user-device evidence records remain unchanged.

## E-M4-003: first M1 on-device report (unplugged)

[Full evidence and source-audit record](runs/E-M4-003.md). User supplied the generated summary from build 1a68f40a377be7a8d0feac1bf05b6170d87659b9-dirty, iPad16,5 / OS 27.2, selected Balanced/Sharp Efficient, 2128 × 1600 launch size, 60 cap, Driver Default, detailed profiling off; user confirms unplugged. Session duration 405.467942 s; retained host cadence 55.421611 FPS; p50/p95/p99 16.7/20.9/21.1 ms; maximum 587.229 ms; counts >20/>33.33/>50 ms 6087/31/28; 69 slow pipeline calls, worst 312.790 ms; coarse battery estimate 0.0 pp/hour; collector/export drops 6/0.

No JSON or raw attempt log yet. Included duration, frame count, actual swapchain dimensions, CPU/memory/thermal readings, battery levels and timestamp correlation are unavailable from this summary. A nonzero valid battery sample duration with no reported decrease can produce zero; it is not zero energy use. The slowest pipeline call and worst interval are not demonstrated to coincide. Native drop categories are not separated. Record this as partial M1 on-device evidence, not completed monitoring validation, a controlled performance regression or a power saving. Next: inspect this exact session's JSON and attempt log before more device experiments; retain M2/M3 and Adaptive energy validation.

E-M4-003 log supplement: accompanying pasted text confirms actual 2128 × 1600 swapchain/drawable through resume, applied Balanced normal/background QoS, Driver Default synchronous=1/prefill=0/limit=64, cache accepted 11,580,626 bytes and later checkpoint 12,266,295 bytes, and nominal thermal classifications in shown windows. A 245.04 ms interval closely corresponds to a 243.308 ms pipeline call, whereas the 587.23 ms interval's window reports only 0.317 ms of creation (one call, none slow or in-flight). Multiple approximately 50–58 FPS windows have cheap/no pipeline creation and p95 near 20.9 ms. This establishes separate pipeline and non-pipeline investigation needs, without identifying CPU/GPU/pacing cause or monitoring overhead. A 636.38 ms window is lifecycle-adjacent and must be labelled separately. JSON and complete session boundaries are still required; see the full record for representative windows and remaining limits.

## E-M4-003 JSON audit completed

[Audit](runs/E-M4-003-JSON-audit.md) and [original JSON](runs/E-M4-003.diagnostics.json), SHA256 c83febcc9c055d87c3da0fabe9f10d79e8960387a5839f671eb2e218ed925c5f. All checked window-to-summary counts/durations/maxima reconcile. The 55.421611 FPS is 21,350 retained intervals / 385.228790 s, not 405.467942 s wall duration. There are 16.537365 s of recorded exclusions; startup is included and mission boundaries are unknown. All 15 battery levels are approximately 70%, state unplugged; estimate spans 309.853644 s with no reported decrease. Brightness 100%, thermal classification nominal, LPM off; weighted CPU activity approximately 63.049% of one logical CPU; maximum observed footprint 3.592244 GiB. These are not energy/power or actual displayed-frame measurements.

Six native drops remain uncategorised. Source audit shows contention on any native record can reset frame continuity, potentially omitting an interval. This prevents full cadence/hitch-coverage validation despite correct arithmetic. M1 collection/reporting refinements now precede the next baseline and M2/M3 interpretation. Some long pipeline calls may be off-critical-path; the JSON cannot decide that versus missing intervals. No controlled regression, zero-power conclusion, monitoring-overhead result or optimisation benefit follows from this session.

## E-CI-ITER-002 — corrected monitoring and experiment tooling

Source 6c4fef3d20178f8b4a49a157a5863b2de981a616: [run 40178749888](https://github.com/aaULTra/Husk/actions/runs/40178749888) passed 104 checks (graphics 18, resolution 6, source efficiency 6, worker policy 29, Vulkan timing 8, pipeline store 9, driver profile 9, efficiency observer 12, Swift calculations/events/JSON 1, pipeline diagnostics 6), iOS compilation and validated IPA packaging. [Artifact](https://github.com/aaULTra/Husk/actions/runs/40178749888/artifacts/12593800140); archive SHA256 ebc30a6ea14e8be300296e796cdee635cebc854bcf69d8d3f717e548146b0ec5. Packaged identity retains documented -dirty suffix.

M1 tests now cover retained long intervals despite host/event contention, actual loss categories/maxima, queue overflow, stale-session rejection, battery uncertainty, phase/event tags and occurrence/record time. M2 tests cover partial signatures/handle changes/specialisation/teardown/passive feedback/bounded recording. M4 tests cover actual wrapper sleep bypass, unchanged engine request and thermal/30 FPS safeguards. M8 tests verify yield counting only while included monitoring is enabled.

Earlier run 40167973725 passed then-current checks but failed iOS compilation on Swift memberwise argument order; corrected run 40178005735 passed before the final M8 addition. Preserve failure history. These CI records are implementation/build evidence only; no new device performance, GPU, energy, thermal or overhead result is claimed. E-M4-003 remains the last supplied device evidence.

## E-M4-004 — corrected monitor, gameplay and reported warmth

[Full audit and original files](runs/E-M4-004.md). JSON SHA256 07c79b71e62c027adc830a4c7218c81bbeb83b39f274f566bd6342f10c3e6232. Build 6c4fef3-dirty, 2128 × 1600/Balanced/Driver Default, experiments/profiling OFF, unplugged/100% brightness. 57.172706 host FPS, p50/p95/p99 16.7/20.9/21.0 ms, maximum 474.380 ms, 40 slow pipeline calls (worst 254.135 ms), frame/host/event drops 0/1/0. Counts/durations reconcile; 67 windows, 373 samples, 98 events. Native battery reports one 50% ->45% step; approximate 27.5 pp/hour is coarse, not measured power. User reports warmth relative to not playing; numerical temperature unavailable, sampled thermal classification nominal.

MetalFX spatial capability is true; no upscaling is active. Weighted process CPU approximately 62.81% of one logical CPU and yield rate approximately 5.59 observed calls/s do not establish GPU limitation or spin-dominated waste. Pipeline and non-pipeline paths both persist; cache hit/identity remain unavailable with identification OFF. This supports partial M1 on-device correctness, not overhead acceptance or efficiency benefit. Keep subsequent UI-01 builds separate from this run's source.

## E-CI-UI-001 — UI-01 correction build

[Run 40181321395](https://github.com/aaULTra/Husk/actions/runs/40181321395) at 02c89cb8da7d9b3966f0da7260bad677ff3e6da2 passed 105 checks, iOS build and IPA packaging. [Artifact](https://github.com/aaULTra/Husk/actions/runs/40181321395/artifacts/12593913066); archive SHA256 a8f44504c57d04d945d7d2ef39e1be46acd7ae3449b32ba8ec3db40b61dfe99a. An initial standalone geometry test failed for missing CoreGraphics import and was corrected; the final build includes the later hosted window-control clearance. No physical screenshot acceptance or performance/energy benefit is inferred. E-M4-004 remains evidence from the earlier 6c4fef3-dirty build; the host window button itself remains host-owned.

## E-UI-002 — user confirmation of status-bar correction

2026-10-25: user states “you fixed the status bar stuff.” This is user-reported status-bar acceptance, not a new captured diagnostic session. Exact tested build SHA, new screenshot and window/rotation/gesture/lifecycle matrix are not supplied. The correction candidate was build-validated at 02c89cb (E-CI-UI-001); do not assign that SHA as a newly verified test fact. UI-01 remains partial for broader coverage; no host-button removal or performance/energy benefit is claimed. Sequence: UI-01 -> M1 usability/M6 sizing, while M3/M9 preparation and M2/M4 proceed under the current master plan.

E-M4-004 interpretation reaffirmed: pipeline and independent non-pipeline faults are observed, dominant electrical cost remains unknown. Its 27.5 pp/hour is a coarse single battery step, not a verified sustained rate. CyPort-style QoS energy benefit and MetalFX quality/net cost remain unverified.

## E-CI-GPU-001 — GPU-BATCH-1 sampler/group-export build

Source 17688ce3f2f7059bdce865bed6be836deed4903c, [run 40184166033](https://github.com/aaULTra/Husk/actions/runs/40184166033), **119 passing checks**, iOS compilation and IPA packaging. [Artifact](https://github.com/aaULTra/Husk/actions/runs/40184166033/artifacts/12595910369), archive SHA256 ea2a2e279d0260da0f1479ab125ea0418971b26cb140620297a5aa3561f6bcae; packaged source retains -dirty from staging. Checks cover collector budgets/capacity/epochs/nonblocking losses/invalid timestamps/out-of-order completions, actual queue forwarding/missing-export fallback, Apple factory chaining/exact-queue filtering/teardown, Swift clipped GPU interval union/JSON, and colliding pipeline groups, plus prior required regressions. First source 4828b338/run 40183894409 also passed but predates clock alignment refinement.

[Build-specific handover and completion gates](builds/17688ce3f2f7059bdce865bed6be836deed4903c.md). This is implementation/build evidence, including a fake-queue Apple adapter executable, not a real M4 GPU capture or hardware performance/energy acceptance. No new device session is supplied. M9-A path/requirements mapped; lower scene input and safe full-output integration remain open. Next request combines M3/M2 in two focused sessions, retaining all baseline behaviours and later experiments.

## E-FEEDBACK-001 — no perceived energy-efficiency improvement

2026-10-25: user reports “Felt no improvement in energy efficiency.” Preserve this as subjective negative feedback; no new report/JSON, build identity, test duration, settings, battery/power or temperature measurements accompany it. The latest delivered candidate is GPU-BATCH-1 source 17688ce3, but the tested SHA/session and enabled diagnostics are not verified by this message. Do not assign this feedback a fabricated measured delta or interpret it as confirmed regression/zero benefit.

No energy acceptance gate is passed by this feedback. GPU-BATCH-1 added measurement infrastructure, not an adopted energy optimisation; its implementation/build completion is distinct from the unresolved user objective. Next obtain the already-recorded report.md/diagnostics.json (both pairs if available), check actual GPU validity/coverage/clock mapping and pipeline groups, then choose a specific M3 -> M9 or M2/M4 intervention. Do not request another general gameplay run before examining available files. Keep M1 overhead, M7 Adaptive versus Balanced energy, actual MetalFX integration and all other unfinished work open.

## E-CI-AUDIT-002 — worker/render observability and offline evidence tooling

Source 1950280348c4030aaecadf17d3a68444b6381f86, [run 40219623804](https://github.com/aaULTra/Husk/actions/runs/40219623804): **137 checks passed**, iOS compilation and IPA packaging. [Artifact](https://github.com/aaULTra/Husk/actions/runs/40219623804/artifacts/12609396972); archive SHA256 bfbdd8767ec2cb07274911177350bf8985e4486403166d1544eec6dee0948187, packaged -dirty from staging. Added checks exercise controller request versus observed cap/rollback and query failure; actual Vulkan inventory wrapper forwarding, default-off bypass, exact-project scope, capacity/contention loss; archived export arithmetic/GPU overlap/condition uncertainty; and full weighted progress validation. Local 134 checks plus three Apple-only checks all pass in CI.

[Source-specific handover](builds/1950280348c4030aaecadf17d3a68444b6381f86.md) and immutable progress snapshots establish approximately 21% overall weighted roadmap completion (21.17 exact gate arithmetic, first scored baseline), M4-only approximately 24%, Duo 0%. No device result is inferred. User currently lacks iPad access; hardware/runtime/overhead/energy/MetalFX integration gates remain pending. Preserve E-FEEDBACK-001 without turning subjective no-improvement into a measured regression. No new physical test requested now.

## E-CI-FEEDBACK-003 — stage-aware cache evidence and partial-v2 build

Source af11056edcfa565042884a801c01d3cc3826c557, [run 40235677996](https://github.com/aaULTra/Husk/actions/runs/40235677996): **156 passing checks**, iOS compilation and IPA packaging; [artifact](https://github.com/aaULTra/Husk/actions/runs/40235677996/artifacts/12615520093), archive SHA256 4e83e77269e9d2d65d92ce7ff61cc5156af8f3459acb4eb0509d39fc41639a5e. Packaged -dirty is from staging. Supported extension/chain requests remain explicit diagnostic opt-in; valid stage-library hits are distinct from pipeline-level hits. Tests cover original device/pipeline forwarding and fallback, no retry on device loss, lifetime/allocation bounds, existing guest feedback, ignored state pointers, stage identity/masks and schema-v5 audit, with earlier suites retained.

[Build handover/progress snapshots](builds/af11056edcfa565042884a801c01d3cc3826c557.md) retain overall ~21% (21.17 exact, +0 points), M4-only ~24%, Duo 0%; no hardware/energy gate newly passed. MoltenVK v1.4.2 source findings are research evidence: extension advertised, stage feedback can reveal library reuse, and separate low-input/present-buffer integration would require a dedicated driver design. They are not actual new M4 feedback, cache-hit, GPU-bound or MetalFX measurements. No user action requested while hardware is unavailable.

## E-CI-SPATIAL-001 — separate-driver MetalFX prototype

Source 9d298c5c7c56af87c715ba2b8ad03111a48dcbac, [run 40244864869](https://github.com/aaULTra/Husk/actions/runs/40244864869), **161 passing checks**, exact upstream-source transforms, Apple scaler ABI/failure tests, separate pinned driver compilation, exported vkHuskSpatialConfigure/vkHuskSpatialSnapshot symbols, iOS app build and IPA packaging. [Artifact](https://github.com/aaULTra/Husk/actions/runs/40244864869/artifacts/12617843814); archive SHA256 1fda7f7920a09a9d85982450c5298b91e71dda706a79bd50123518c196b58aab, expires 2026-11-01. Packaged -dirty reflects donor staging/XcodeGen/optional framework embedding.

Experimental upstream is v1.4.2/db66022459ffb663aa2b50f6b018bc2e124f5edf; spatial integration digest 06ccc3562c7d4e35a5bac09c96b81b9e76414aefed977caa7d698f395ebaefc9. Prototype provides per-image lower textures/scalers, original waits/present/signals, touch mapping, driver/cache isolation and schema-v6 counters. Original driver and baseline remain default. [Handover](builds/9d298c5c7c56af87c715ba2b8ad03111a48dcbac.md), [design/gates](17-metalfx-spatial-prototype.md).

This is compilation/contract evidence, not actual M4 upscaled pixels, safe lifecycle, visual quality, FPS, GPU cost, power or heat evidence. S1–S6 6/6, physical 0/4, benefit 0/3. Whole M9 implementation 4/6 and weighted whole-milestone score 20%; overall 21.77% (+0.60 points), M4-only ~24%, Duo 0%. All prior subjective no-improvement evidence and unfinished Adaptive/shader/pacing/driver/device work remain. No current user action while hardware is unavailable.

## E-M4-005 — MetalFX A and restarted B

[Full four-file review, provenance, raw reports and lossless JSON archives](runs/E-M4-005.md). 9d298c5c-dirty, M4/OS27.2, 1696×1280 guest input ->2128×1600 configured/validated scaler output; 18046/10455 encodes, zero scaler failures; 59.728/59.544 host FPS. Both are GPU/inventory diagnostic runs, not energy A/B. User reports restart before B and later corrects visual concern to probably same/no issue noticed. Preserve earlier uncertainty as history, not a confirmed regression.

M3-D1 bounded B queue/timestamp/exclusion evidence and M9-D3 subjective ordinary-play gate pass for the named conditions. [Evidence ledger](progress/E-M4-005.ledger.json)/[score](progress/E-M4-005.score.json): overall24.02% (~24%), +2.25 points; M4-only~27%, Duo0%. No energy credit. Both shader-associated and unresolved/cumulative-burst stalls remain; worst B411.843/410.309ms. Inventory saturation hides scene-size records; raw clock mapping has a small A boundary ambiguity; new offline audit/11 tests preserve/correct estimates without changing the IPA. Actual internal scene dimensions, matched quality/GPU/energy, lifecycle and Adaptive savings remain unverified.
