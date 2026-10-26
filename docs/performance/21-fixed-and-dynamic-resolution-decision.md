# M9 fixed-budget and dynamic-resolution investigation — decision DYNAMIC-1

2026-10-26. Scope: whole-roadmap M9-I6 research/decision deliverable. This completes a retained engineering investigation, not dynamic-resolution implementation or a validated optimum. E-M4-006 actual rendering commands and the fixed-profile code are the evidence. Preserve future GPU-driven dynamic resolution, independent of MetalFX, as an explicitly deferred experiment.

## What exists

Manual output budgets65–100% and the known2128x1600 M4 reference are implemented. MetalFX offers independent80/85/90/95% input dimensions with that selected output unchanged. Aligned inputs are1696x1280,1808x1360,1912x1440,2016x1520. None is established as the device's energy optimum. E-M4-006 compares only80% ON with full-resolution OFF; no controlled comparison of all budgets, numerical image equivalence or sustained electrical savings exists. The older1784x1336 output run is a separate uncontrolled experiment.

The actual lower-resolution HDR/colour/depth/legacy-area/post-process requests shrink with the input budget, alongside directly observed scaler textures. This is evidence the route affects resolution-dependent rendering, not merely a smaller presentation label. It does not prove every pass or UI element scales, the internal identity of every render target, or a net power reduction after the scaler/presentation overhead. Some1696x1440 requests also occur; do not forcibly resize them on the assumption they are waste.

Sources: husk-tl-ue4-graphics.c resolution fractions and preset CVar requests; husk-tl-spatial.c aligned input dimensions; TLAppSettings.swift stored manual budgets/restart controls; husk-tl-vulkan.m launch preflight; HuskSpatial.inc configure/live-image guard and per-image owned resources. [Paired empirical record](runs/E-M4-006.md).

## Separate routes considered

1. **Fixed original rendering budget, no MetalFX.** Already manually selectable; full-resolution reference remains protected. Can eventually select a device-specific tested budget, but current data does not support automatically changing it or calling fewer pixels an efficiency win.
2. **Fixed lower input plus spatial MetalFX.** Implemented separately/default OFF. Maintains selected output and has a working mechanism with subjective ordinary-play acceptance. E-M4-006 does not establish an electrical/net GPU benefit, so no automatic/default adoption.
3. **UE internal dynamic scene percentage, independent of MetalFX.** In principle can resize scene rendering while retaining full-resolution output/UI. Current Efficient preset requests r.ScreenPercentage=100 and r.DynamicRes.OperationMode=0; game acceptance/live engine control remains unverified. Translation code does not own the engine's scene graph, appropriate per-frame GPU estimates or authoritative live CVar setter. Adding a host-cadence-driven quality reducer would confuse CPU/scheduling/shader/presentation stalls with pixel cost.
4. **Dynamic whole-image MetalFX input.** The current driver accepts configuration only with no live images and owns fixed per-swapchain-image textures/scalers; host/V4/native-window launch dimensions are prepared together. Changing the saved percentage mid-frame cannot safely implement this route. It requires an engine-supported resize/percentage path or a separately designed resource-generation/synchronisation protocol, while protecting outstanding Vulkan/Metal image users and preserving selected output/aspect/input. It must not add queue-idle stalls on ordinary frames.
5. **Temporal MetalFX.** Requires trustworthy motion/depth/jitter/history/colour data and engine integration absent from the current whole-image spatial path. Keep as separate research; not a substitute for missing dynamic-resolution measurements.

## Why the current GPU feed cannot safely drive an automatic controller

The sampler captures bounded factory-created game command buffers for1 second every10 seconds, with a256-handler/window budget and incomplete queue/buffer coverage. Intervals overlap and can include waits. There is no complete frame-to-command-buffer graph or authoritative scene-only GPU cost. Raw export cap and lost/invalid callbacks further limit the supplied long run; CORE-BATCH-4/earlier aggregate work improves retained summaries, not frame attribution. Host submit duration includes CPU encoding/waiting and is not GPU execution.

A controller reacting to~20.9ms host intervals could lower quality while the actual cause is engine/host limiting, scheduling, game-thread work or first-use pipelines. E-M4-006 has similar cadence ON/OFF and higher process CPU in the longer ON run, with confounded scenes/cache/temperature. Those observations justify investigation, not a GPU-bound diagnosis or automatic resolution cut. A60FPS cap does not independently prove headroom.

## Retained decision and reopening conditions

Keep the verified selected output and current manual options. Do **not** implement or enable automatic dynamic resolution in this batch, and do not treat spatial scaling as a measured energy improvement. This is an evidence-supported scope decision rather than abandonment. Preserve manual rollback and the separate original/experimental drivers/caches.

Reopen independent dynamic scene percentage when the engine's live support and actual scene dimensions are verified, a representative per-frame/scene GPU-cost signal is available, and a controlled fixed-budget comparison demonstrates a plausible quality/net-work trade-off. Reopen whole-image dynamic scaling only after a safe resource-generation/resize/lifetime design and sustained net-GPU/power evidence justify the complexity. Any future mode requires explicit user control, stable hysteresis, no rapid visible oscillation, and matched visual/p95/p99/energy acceptance. No numeric control thresholds or device defaults are selected from today's partial data.

M9-I6 can be accepted for this investigation/retained decision after source/link review; **RES-01 dynamic resolution remains unimplemented**. M9 device/benefit gates remain open. M4 and future Duo need independent evidence; no M4 budget, worker policy or optimal power assumption transfers to Duo. All earlier shader, pacing, submission, worker and translation investigations remain tracked.
