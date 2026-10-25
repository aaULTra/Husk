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
