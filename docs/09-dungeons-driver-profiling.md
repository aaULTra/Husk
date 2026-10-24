# Opt-in MoltenVK activity profiling

The current M4 logs frequently show 60 FPS at a 2128x1600 presentation surface,
with intermittent inventory/firework stalls and expensive pipeline creation.
They do not establish that GPU rendering, command encoding or synchronization is
the main limitation. An older low average FPS must not be interpreted as the
same excess work on every frame; a small number of stalls can lower the average.
Engineering-priority scores are judgments, not measured performance evidence.

## Implementation

Game Graphics > Driver Phase Profiling defaults off. Enable it before a full
restart to request MVK_CONFIG_PERFORMANCE_TRACKING=1 before MoltenVK loads.
MoltenVK's own periodic performance log is disabled for this mode; Husk copies
the statistics into its attempt log on the existing roughly 10-second cadence.
The option is forwarded through fullscreen and floating-window launch paths.
It does not add Metal capture, GPU queries, readbacks or queue-idle waits, change
resolution, submission configuration, command encoding or buffering, or claim
to reduce power. Activity tracking adds CPU overhead; use short diagnostic runs.

The reader uses vkGetVersionStringsMVK and vkGetPerformanceStatisticsMVK directly
from the bundled library. It accepts only version 1.4.2 and the complete 1152-byte
MVK_PRIVATE_API_VERSION 43 statistics layout. A mismatched version, missing API,
short result or VK_INCOMPLETE data read disables sampling. The NULL-output size
query may return SUCCESS or INCOMPLETE, but its reported size must match exactly.
No size-compatible prefix is interpreted. Updating MoltenVK requires rechecking
the layout and source semantics before extending support.

The first live VkDevice is sampled, with a mutex protecting its lifetime across
the short statistics query. Reporting skips a busy mutex; device teardown clears
the handle under the same mutex before invoking the real destroy function. Logs
are written after releasing the mutex. Device replacement resets count baselines.
No Metal command-buffer completion is waited for by the reader.

Phases include SPIR-V-to-MSL conversion, Metal-library compilation, function
specialization, Metal-pipeline compilation, cache serialization, Vulkan-command
encoding, submit-to-encoding delay and drawable retrieval. Counters are cumulative:
`new` is the count since the previous sample, while `avg` and `max` are lifetime
aggregates and `last` is the latest completed activity. A count reset/wrap is
labelled. Nonfinite/negative duration fields are not emitted. Memory trackers are
not printed as milliseconds. Nested/parallel phases cannot be summed to compute
frame cost, and cache-retrieval counts are not cache-hit measurements.

Critically, MoltenVK's mtlCommandBufferExecution measures elapsed host time from
commit setup to its completion callback. Husk labels it
commit-to-completion-callback-latency, not GPU execution. It can include waiting
and callback scheduling. Presentation callback latency has the same caveat.
Actual Metal GPU execution duration requires completed command-buffer GPUStartTime
and GPUEndTime (or appropriate Metal/Instruments capture), which this hook does
not expose. This is driver-phase profiling, not a full CPU/GPU trace, utilization
measurement or automatic bottleneck classification.

## One short device check

Keep the visually preferred resolution (M4 Automatic fullscreen target 2128x1600),
60 FPS and Driver Default submission. For this diagnostic run use Balanced worker
scheduling so an adaptive trial does not change scheduling while measuring.
Enable Driver Phase Profiling and fully close/reopen Husk. Keep LPM off and do
not toggle it during the run. Play a familiar section for about one minute, open
inventory a few times and use the firework ability twice, noting first-use versus
repeat hitches. Export the complete attempt log including startup and normal pause.
Two to three minutes is a practical initial sample, not a sustained thermal test.
The log should show an accepted ABI and populated driver-phase counters. If it
reports unavailable/mismatched or no new activities, send that result rather than
repeat blindly. Disable profiling and restart for ordinary performance/heat tests.
Do not compare energy or frame cadence from profiling-on to profiling-off runs
as if instrumentation had no overhead. Real GPU/CPU traces may still be needed
if the phase counters do not distinguish the limitation.

## Primary references

- https://github.com/KhronosGroup/MoltenVK/blob/v1.4.2/MoltenVK/MoltenVK/API/mvk_private_api.h
- https://github.com/KhronosGroup/MoltenVK/blob/v1.4.2/MoltenVK/MoltenVK/Vulkan/mvk_api.mm
- https://github.com/KhronosGroup/MoltenVK/blob/v1.4.2/MoltenVK/MoltenVK/GPUObjects/MVKQueue.mm
- https://github.com/KhronosGroup/MoltenVK/blob/v1.4.2/Docs/MoltenVK_Configuration_Parameters.md
- https://developer.apple.com/documentation/metal/mtlcommandbuffer/gpustarttime
- https://developer.apple.com/documentation/xcode/capturing-a-metal-workload-programmatically
