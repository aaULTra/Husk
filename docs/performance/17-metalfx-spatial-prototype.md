# M9 Spatial prototype — implementation batch

2026-10-25. Checklist M9-SPATIAL-v1. The user explicitly requests substantial implementation, including larger changes while hardware is unavailable. This authorises a default-off prototype before M3 physical evidence; it does not waive device, visual, overhead or energy acceptance. Findings were reported before renderer edits.

Sequence: prior M1–M3 observations and M9 source mapping -> separate pinned-driver prototype -> correctness/visual/GPU checks -> matched unprofiled energy comparison -> adoption only with evidence. Earlier shader, pacing, scheduling, submission and device investigations remain independently selectable and unfinished.

## Protected path and implementation

The original checksum-pinned donor MoltenVK framework stays embedded and is selected when the option is OFF. A separately named HuskMoltenVK framework is compiled from upstream v1.4.2 commit db66022459ffb663aa2b50f6b018bc2e124f5edf. Exact source transformations refuse drift. A SHA256 manifest identifies integration inputs. No driver-version upgrade is implied. Ordinary source builds without the optional framework retain the baseline and decline activation.

Game Graphics has a default-OFF MetalFX Spatial · 80% Input option, saved per game and requiring full restart. The original chosen launch dimensions become output. Native exact Dungeons activation and driver/scaler preflight must succeed before effective launch/ANativeWindow/HLE/V4 dimensions are reduced. At 2128 × 1600 output the aligned input is 1696 × 1280. This is a whole-image prototype, including HUD/text; scene detail/quality equivalence is unverified. It is not GPU-driven dynamic resolution. No temporal scaler is supplied.

Each swapchain image owns a private tracked lower-resolution texture and a cached spatial scaler. Rendering still acquires the original display drawable, preserving the existing back-pressure point. The headless field is untouched. Scaler input/output usage requirements and actual output format/dimensions are checked. SDR BGRA UNORM/sRGB use explicitly chosen colour processing; HDR, nonidentity transforms, nonopaque composition, multilayer/mutable/extension-chain swapchains are rejected. Such errors must remain observable, not silently turn into unscaled low-resolution presentation.

Scaling is encoded on the retained original presentation command buffer, after existing render-completion waits, before original scheduled presentation and semaphore signal/commit. Original drawable/fence/image retain and completion handlers remain. Per-image scaler encoding is serialised independently. Input/scaler cleanup follows image destruction and retained Metal command-buffer references. No new queue, queue-idle wait, readback or per-frame scaler creation is added.

Touch coordinates map from selected output pixels into the actual accepted input. Baseline cache files stay untouched; experimental persistence uses husk-pipeline-cache-spatial-v1 with existing compatibility guards. Export schema v6 adds actual driver configuration/input/output/encode/failure counters and build manifest, while preserving older fields. M9-SPATIAL logs identify selection, preflight and acceptance; zero encoding or failures must not be presented as successful game upscaling.

Preflight refusal leaves the original dimensions. A later unsupported swapchain/allocation/encode failure is explicit; disable the option and fully restart to restore the original driver, dimensions and cache namespace. Correct behaviour after all lifecycle cases still requires physical validation.

## Acceptance and current limits

Implementation/build S1–S6:
1. Bounded, versioned configuration/dimension ABI and preflight failure preservation.
2. Per-image texture/scaler creation, ownership and cleanup.
3. Original presentation ordering/lifetime and strict format guards.
4. Default-off controls/all launch paths, touch mapping and driver/cache isolation.
5. Structured activation/input/output/failure/build evidence.
6. Executable portable/Apple checks, source-pin transform validation, driver/app build and IPA packaging.

Device D1–D4: actual useful lower scene input/baseline output and stable 60 FPS; colour/HUD/detail/motion/input/audio; pause/resume/window/resize/restart/rollback; GPU-timing correctness and acceptable monitoring overhead.

Benefit E1–E3: matched total GPU work including scaler and pacing; repeated unplugged electrical/battery comparison with diagnostics OFF; external ambient/surface-temperature comparison with acceptable quality. All device/benefit gates pending. Smaller input and successful encoding do not prove power savings. Do not close Adaptive energy versus Balanced.

The local workspace became unavailable during implementation; final candidate must be compiled/tested in Apple CI rather than claiming local checks. No user test is requested while the iPad is unavailable. Existing exports should be examined first. A later short correctness smoke precedes any sustained energy comparison.

## Final implementation/build evidence

Source `9d298c5c7c56af87c715ba2b8ad03111a48dcbac`, [Apple run](https://github.com/aaULTra/Husk/actions/runs/40244864869): **161/161 checks passed**, including actual host forwarding/touch/fallback code, driver format guards and Apple scaler ABI/failure checks; exact source transforms, standalone driver exported symbols, app compilation and IPA packaging passed. S1–S6 build checklist 6/6. No real MetalFX GPU render or iPad lifecycle check was run by CI. D1–D4 0/4 and E1–E3 0/3 remain pending. Whole M9 implementation 4/6, whole milestone 20%; broader lifecycle/failure coverage and legacy M9-A R3/R4 remain open. [Source-specific handover](builds/9d298c5c7c56af87c715ba2b8ad03111a48dcbac.md).
