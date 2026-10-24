# Guarded worker trial and upscaling investigation

## What the data supports

The M4 log reports normal Unreal TaskGraph workers already requesting Default
QoS and background workers at Utility under Balanced. It does not demonstrate
CyPort's alleged highest-priority-worker problem, actual core placement, energy
use per job or which individual jobs are on the critical path. Apple QoS
influences scheduling; no public core pinning is claimed here.

The 1TB 13-inch M4 iPad specification lists four performance and six efficiency
cores; iPhone Duo lists two super and four efficiency cores. The policy uses the
runtime total processor count only as a capacity hint: >=10 reserves two named
normal workers at Default, otherwise one. It is not a topology detector, a job
classifier or proof of optimal allocation. High-priority, game/render/audio and
unknown roles retain their original scheduling. Normal workers without an
unambiguous numeric index never receive the extra Utility cap.

## Adaptive Trial (Experimental)

Balanced remains the saved/default choice. Adaptive Trial is a separate opt-in
mode for the exact Dungeons project. It begins with the existing Balanced caps.
At least 20 seconds of valid sampled windows at >=59 FPS, p95 <=20.5 ms, maximum
interval <=50 ms and nominal thermal state admits extra Utility caps on recognised
normal workers outside the capacity-hint budget. Pipeline creation is allowed
when individual host calls take <=2 ms and their summed host time is <=0.5% of
the window (50 ms in 10 seconds), with no call still in flight at the sample.
The previous zero-pipeline rule never admitted a trial in the supplied log,
even during healthy windows with only cheap pipeline calls. These revised
thresholds are conservative hypotheses, not measured CPU headroom or an energy model.

The controller requests a return to Balanced on unhealthy sampled cadence,
expensive pipeline creation, thermal pressure, Low Power Mode transition or a sampling
discontinuity. A quicker per-frame guard reacts to six consecutive intervals
above 20.5 ms, or one interval above 50 ms. A failed trial waits 60 seconds before
readmission. Pausing releases the extra caps and clears admission progress.
Completion of an individual pipeline call above 2 ms also requests rollback
without waiting for the next reporting window. No baseline QoS is raised to
compensate for slow frames. Waiting reasons and trial transitions are logged;
repeated identical waiting reasons are rate-limited to once per 30 seconds.

Workers apply requests to themselves at condition/semaphore waits, futex returns
or explicit guest yields. No cross-thread QoS writes, live pthread handle
registry, signals, affinity masks or thread suspension are used. Busy workers
may not reach a checkpoint immediately: rollback is a request, not a guaranteed
instant rescue. Failures preserve accurate state and retries are rate-limited.
Role renames restore original QoS/relative priority before reclassification.
Ordinary Balanced/Observe/Default paths do not run the adaptive controller.

The cadence guard cannot tell whether a regression comes from worker caps,
GPU load, I/O or an unrelated hitch. It deliberately backs off without claiming
causality. Conversely, stable cadence does not prove lower heat or energy.
Thread State/Time Profiler and energy/thermal measurements remain necessary for
those conclusions. It is more guarded than an unconditional fixed worker split,
not demonstrated universally faster or more efficient than CyPort.

## Resolution controls

A Custom option adds a 65–100% slider in 1% increments, alongside existing presets.
The selected percentage scales both launch dimensions, with UE4 alignment; it
preserves texture/AA settings, not all spatial detail. Full restart is required.
No automatic perceptual minimum, dynamic in-mission resolution or identical
appearance is promised. Device/display budgets remain heuristic defaults.

This is Husk's host control, not a claim to have enabled the APK's own slider.
The native game's r.SetRes/UGameUserSettings paths are intentionally overridden
because the supplied game repeatedly requests 1280x720 and previously fell to
816x720. Simply removing those guards would reintroduce the original problem.
Supporting the native slider needs verified semantics and aspect-ratio handling.

The Sharp presets replace the unused Display resolution picker with "See Game
Graphics". Automatic is labelled "Reduced Resolution", and a Fullscreen Target
shows the estimated landscape size for the next launch. Saved values and output
budgets are unchanged. A settings log records the selected controls separately
from the actual swapchain dimensions, so selection/application mismatches can
be distinguished from the old inactive Native label.

## Cache checkpoint and stall follow-up

Cache snapshots now track a per-device mutation generation. Cache creation,
pipeline creation using a tracked cache, and destination-cache merges invalidate
the saved generation. Failures are also treated as possibly mutating because
Vulkan can return partial pipeline results. Repeated pauses without a mutation
skip temporary-cache creation, merge, serialization and disk replacement; the
async entry point also skips creating its worker thread. Failed saves remain
dirty. Mutations during unlocked disk I/O remain dirty, and a device incarnation
serial prevents an old snapshot from marking a recycled device handle clean.
This reduces redundant pause work, not first-use shader compilation time.

Cache diagnostics distinguish game-supplied initial bytes from Husk-restored
bytes accepted by the driver. Acceptance is not proof of shader cache hits.
Each reporting window includes total/max pipeline host time, slow-call count and
in-flight count. At most one worst slow call is detailed per reporting period,
including batch size, result and store-lock wait. Recording uses try-locks and
never waits for a diagnostic lock, adds GPU synchronization or logs on every
pipeline call. A missed try-lock can omit the detailed record; aggregate counters
still update. Durations can overlap and include CPU scheduling delays; neither
the detail nor an inventory/firework coincidence proves exclusive stall causation.

## Device check for this revision

Keep the working graphics and resolution selections; Automatic on the supplied
M4 fullscreen display should still produce 2128x1600. Keep Driver Default and
the 60 FPS target. Enable Adaptive Trial, fully restart Husk, and keep LPM and
charging conditions fixed for a short repeatable session. Allow at least 20
seconds of qualifying windows, then open inventory and use the same firework
ability that previously hitched. Export the complete log, including startup
and a normal pause. The log should explain admission or refusal, worker changes,
any rollback, restored cache acceptance and checkpoint outcomes. Compare the
first and repeated uses within the session, without assuming repetition or
cache acceptance guarantees hitch removal. Return to Balanced and restart if
the trial causes persistent stutter. This is a guarded device experiment; the
portable checks and successful IPA build cannot establish an energy/FPS gain.

## MetalFX feasibility

MetalFX is not wired into the Vulkan presentation path by this change. Spatial
upscaling is the most feasible first candidate: it needs an anti-aliased,
tone-mapped color input and a distinct larger output texture. Temporal scaling
additionally needs suitable depth, motion, jitter/history handling and correct
reset behaviour. The current final-swapchain hook does not supply those inputs.

A spatial prototype needs a lower-resolution Vulkan render surface, a native-size
Metal output/presenter, correct Vulkan/Metal completion ordering and resource
lifetimes, and correct color-space/format handling. Sampling a swapchain image
without synchronizing its render completion is invalid. Queue-idle readbacks
would undermine the performance goal. Final-frame upscaling can also soften HUD
text, and upscaling itself costs GPU time; native UI composition is preferable.
Actual MTLFXSpatialScalerDescriptor support must be queried on the running device.
Hardware support alone does not establish this integration or its net benefit.

No MetalFX toggle or artificial capability claim is exposed. Preserve the
working pipeline while developing that prototype separately; measure end-to-end
GPU time, artifacts, frame cadence and sustained energy before choosing defaults.

Primary references:
https://support.apple.com/en-gb/119891
https://support.apple.com/en-gb/148588
https://developer.apple.com/news/?id=vk3m204o
https://developer.apple.com/videos/play/tech-talks/110147/
https://developer.apple.com/library/archive/documentation/Performance/Conceptual/EnergyGuide-iOS/PrioritizeWorkWithQoS.html
https://developer.apple.com/videos/play/wwdc2022/10103/
https://developer.apple.com/documentation/metalfx
