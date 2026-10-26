# Component diagnosis and remaining implementation — schema11 / batch6

Sequence: M1 trustworthy capture -> M2/M3 identify observed costs -> M5/M6/M7/M8/M9 one relevant intervention -> matched M4 correctness/work/net-energy acceptance -> independent M10 hardware baseline. This guide describes available evidence, not a promise that every problem has a software fix.

| Export field / component | Decision it supports | What does not follow | Next plan action |
| --- | --- | --- | --- |
| `component_triage.findings` | Bounded observed problem, confidence, plan IDs and next action | No automatic bottleneck/root cause, passed gate or savings | Follow the named component's evidence/coverage |
| `pipeline_groups_since_launch`, core-v3 coverage | Recognise expensive shader/core-state groups across first/repeat/restart | Incomplete state is not a unique full variant;64-bit hash is not collision-proof; no Vulkan replay key | M2 identify actual recurring expensive groups before M5 preparation |
| `native_pipeline_archive` requirement checks | Successful `FailOnBinaryArchiveMiss` attempts establish native Metal archive requirement was satisfied | Failed API calls have other possible causes; not Vulkan hit/miss, zero compile time or energy savings | M2/M5 inspect raw error, compare same-driver verification-OFF runs and total preparation cost |
| `component_sampling.components` Vulkan scopes | Sampled acquire/submit/present/pipeline caller CPU versus wall | Waiting is not necessarily GPU work; present includes limiter; nested scopes overlap | M3/M6 align GPU/presentation/driver query data; trace a costly scope |
| Same field, JNI | Sampled invoke-boundary cost | It does not cover every compatibility operation or isolate interpreted Java from nested work | M8 trace meaningful JNI call paths before changing bridges |
| Same field, futex/once | Sampled wait/wake/slow-initialisation CPU versus wall | Long sleeping wait is not waste; once includes useful initializer, completed fast path intentionally unsampled | M8 distinguish blocking/scheduling from actual repeated CPU cost |
| `driver_phases` | Already collected opt-in MoltenVK library/MSL/pipeline/encoding/drawable/callback counters | Phases overlap; first query is lifetime; latest/max are not frame GPU execution | M2/M3/M6/M8 deduplicate query serial, align query brackets/exclusions, inspect the relevant activity |
| `samples[].cpu_threads` | Matching thread-ID cumulative CPU deltas, policy joins when identity exists | Process/one-logical-CPU percentage is not device utilisation, watts or P/E placement | M3/M7 reject any exclusion crossing; compare actual treatment and relevant thread share |
| `gpu_records`, `gpu_windows` | Completed sampled Metal buffer GPU-start/end execution and partial union | Not complete per-frame/displayed-frame accounting or GPU percentage/power; missing buffers are unknown | M3 role/clock/coverage audit; M9 include scaler command cost |
| `presentation_clock` | Clock adapter/guest-history observations with retained native feedback | Tiny retained tail/driver estimates are not an entire display trace | M4/M6 independent host/native/display pacing analysis |
| `spatial_upscaling`, `render_inventory` | Actual scaler input/output contracts and associated render command observations | A requested CVar or swapchain size is not independently identified executed scene resolution | M9 useful scene identification, visual/colour/lifetime and matched total GPU/energy acceptance |
| `metadata.runtime_device_inventory` | Actual identifier, logical CPU/RAM, Metal device and maximum display capability | No assumed GPU cores, measured refresh/core residency or future Duo specifications | M3 record capabilities; M10 independently baseline real hardware |
| `delayed_os_reports`, separate MetricKit files | Delayed OS host-process reports, when delivered; wrapper build/bundle are receiver metadata, payload period/build must be inspected separately | Not instant isolated guest-game GPU/power, guaranteed delivery or numerical thermometer | M3 verify LiveContainer attribution and reporting period; keep direct session logs |
| Battery/thermal samples | API levels/states/thermal classifications with timestamps | Flat battery is not zero drain; short step/hour arithmetic is not precise energy; nominal is not cool | M1/M3 sustained unplugged evidence and external power/surface-temperature |

## Controls and collection cost

All new diagnostic controls default OFF. Component sampling is one-in64 per thread/component, not random whole-component estimation. It records only completed included scopes; crossing epochs and contention are disclosed, and a late completion may follow the final snapshot. No additional clock calls/locks/allocations occur in its disabled scope path beyond an atomic gate. Required native controls use launch-time settings and need a complete restart. MetricKit is independently opt-in and may produce no payload during a short test.

Do not enable all diagnostics for an energy comparison. A short diagnostic run may combine component/thread/GPU sampling when their joint overhead is disclosed; then disable them for subsequent normal sustained comparisons. Driver Phase Profiling remains separate and potentially intrusive. Profiles never automatically apply experiments or claim verified benefits.

## Concrete remaining engineering dependencies

- **M2:** determine actual expensive variant coverage on device. Unsupported extensions/RenderPass2 are incomplete; extend only the relevant exposed state rather than guess a replay structure.
- **M3:** verify a supported Instruments/host attachment route and calibrated electrical/surface-temperature evidence. Public thermal classification cannot be upgraded into a numerical thermometer by adding code.
- **M5:** native support/capture/prepare/restart must be observed. Archive descriptors/functions do not remove shader-library front-end work automatically. Include all preparation/loading work in benefit acceptance.
- **M8 encoding/sync:** the latest available stable MoltenVK is already1.4.2. Reopen upgrade benchmarking when a compatible stable release exists. Identify expensive repeated bindings/state/allocations/locks in representative source/trace before choosing a core translation change. Three swapchain images already exist.
- **M9 temporal:** the whole-image swapchain path does not provide identified scene motion vectors, depth, jitter, history and colour contracts. A safe engine data path is required, not just an `MTLFXTemporalScaler` allocation.
- **M9 live dynamic:** require an ABI-safe engine scene-resolution setter, image lifetime/recreation/control boundaries, suitable GPU feedback and user-visible/manual restoration policy. Current launch-fixed hooks and sampled buffer intervals do not supply these. Manual fixed input budgets plus spatial MetalFX already exist.
- **M10:** profile storage/runtime inventory are implemented without guessing capabilities; independent actual Duo baseline/validated defaults/thermal and power results await hardware.

All these investigations stay in PROJECT_PLAN.md. Code/build success and user approval of visuals do not substitute for measured sustained energy benefit.
