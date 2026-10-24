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
At least 20 seconds of valid sampled windows at >=59 FPS, p95 <=20.5 ms, nominal
thermal state and no graphics/compute pipeline creation admits extra Utility
caps on recognised normal workers outside the capacity-hint budget. These are
heuristic admission thresholds, not measured CPU headroom or an energy model.

The controller requests a return to Balanced on unhealthy sampled cadence,
pipeline creation, thermal pressure, Low Power Mode transition or a sampling
discontinuity. A quicker per-frame guard reacts to six consecutive intervals
above 20.5 ms, or one interval above 50 ms. A failed trial waits 60 seconds before
readmission. Pausing releases the extra caps and clears admission progress.
No baseline QoS is raised to compensate for slow frames.

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
