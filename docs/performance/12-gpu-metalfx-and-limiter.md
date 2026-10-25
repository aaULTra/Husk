# M3 / M4 / M9: GPU evidence, limiter experiment and MetalFX path

Sequence: M1 reliable timing/loss reporting -> M2 pipeline identification and **M3 CPU/GPU/presentation evidence** -> independent M4 limiter test and, where GPU cost supports it, **M9 MetalFX spatial prototype**. MetalFX does not require every later scheduling/driver experiment to finish; its prerequisites are trustworthy GPU evidence and a correct interop/presentation design.

## M4 diagnostic implementation

Engine-only 60 FPS Limiter (Diagnostic) defaults OFF. Off retains the existing UE4 t.MaxFPS request, host pacing and FIFO. On bypasses only the extra host 60 FPS sleep in Sharp / Efficient, retaining the engine request and FIFO. Selecting 30 FPS preserves the host 30 cap. Serious/critical thermal host caps remain 30/20 in both modes. The option is forwarded through fullscreen/window launches and requires full restart. Actual engine CVar acceptance must be checked; stop the test and restore Off if it runs uncapped or pacing worsens.

First validate corrected monitoring with both identification/profiling OFF. Then perform matched short dual-versus-engine-only sessions, same route/cache/resolution/brightness/charging state, no simultaneous worker/submission changes. Compare host distributions, CPU samples, displayed cadence where tools permit and later power. The option's existence and lower sleep time are not a benefit. Retain Off unless results justify adoption.

## M3 source investigation

Bundled MoltenVK is staged as a checksum-pinned prebuilt framework. Inspection of v1.4.2 MVKQueue.mm confirms mtlCommandBufferExecution measures a host performance interval from commit setup to completion callback. It does not read GPUStartTime/GPUEndTime. Existing Vulkan/Husk wrappers hold guest VkCommandBuffers, not the completed Metal command buffers MoltenVK creates internally. Metal object export/legacy texture access alone does not supply those existing command buffers or their completion lifetime.

Do not swizzle all Metal objects in the LiveContainer host or create a fresh empty command buffer and call its timing the game's GPU time. Do not block the GPU queue for statistics. Actual GPU execution remains unavailable in the current monitor. Two investigation paths remain:

1. Prefer a short representative Metal/System Trace using a compatible Mac/Xcode/Instruments and a device/host process that can be attached. Verify signing/developer/profiling access and actual LiveContainer process attribution before promising this workflow. Inspect GPU tracks alongside CPU thread states, encoding and presentation waits. Export the trace with build, scene and profiler configuration; use unprofiled runs for sustained energy comparisons.
2. If attachment is unavailable or recurring in-app timing is required, assess a separately built MoltenVK instrumentation change at its own completion handler that exports bounded GPUStartTime/GPUEndTime samples with queue/command-buffer identity. That is a separate driver-build task requiring callback/lifetime/ABI guards, compatible deployment and controlled correctness/overhead tests. Multiple overlapping command buffers do not automatically map one-to-one to displayed frames.

Vulkan timestamp queries are another research route, but require verified queue timestamp support, calibrated units, valid command placement/reset/synchronisation, nonblocking result collection and attribution. Merely reading a timestamp capability is not frame GPU timing.

## M9 preparation in this candidate

Starting an Efficiency Test queries the running Metal device and, on supported OS/SDK versions, MTLFXSpatialScalerDescriptor.supportsDevice. Export records the capability and explicitly states that upscaling is not integrated. No scaler, texture or new rendering pass is created. Hardware support does not demonstrate useful inputs, safe interop or net savings.

A separate spatial prototype needs: a genuinely lower-resolution scene color input; distinct full-resolution output/presenter; verified Vulkan/Metal completion ordering without queue-idle waits; correct texture lifetimes, usage, formats, transfer/color space and tone mapping; and UI/text quality checks. Scaling the final image may soften HUD text, so scene-only/native-UI composition must be evaluated. V4 and baseline output must remain available. Temporal MetalFX additionally requires depth/motion/jitter/history data not exposed by the current final-present hook.

Prototype acceptance: compare total GPU time and measured power including scaler overhead, visual quality at normal viewing distance, p95/p99, input latency and lifecycle correctness. No automatic quality cut or promised percentage saving. Start the prototype after M3 demonstrates a plausible GPU-work reduction; user-device evidence can move M9 ahead of lower-value research without dropping other investigations.

## Sources inspected / implementation references

- MoltenVK v1.4.2 queue source: https://github.com/KhronosGroup/MoltenVK/blob/v1.4.2/MoltenVK/MoltenVK/GPUObjects/MVKQueue.mm
- Private statistics ABI: https://github.com/KhronosGroup/MoltenVK/blob/v1.4.2/MoltenVK/MoltenVK/API/mvk_private_api.h
- Vulkan Metal export semantics: https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_metal_objects.html
- Apple command-buffer GPU timing: https://developer.apple.com/documentation/metal/mtlcommandbuffer/gpustarttime
- Apple MetalFX spatial support: https://developer.apple.com/documentation/metalfx/mtlfxspatialscalerdescriptor/supportsdevice(_:)
- [Existing worker/upscaling analysis](../08-adaptive-worker-and-upscaling.md)

## Additional M3 route found in CyPort source

A subsequent [direct CyPort source review](13-cyport-source-review.md) found its commit interception/completion-handler GPU timestamp sampler. This demonstrates a concrete technique worth assessing, not a safe drop-in Husk implementation. Safe scope, method chaining, command-buffer lifetime, bounded nonblocking recording, clipped/merged interval semantics and LiveContainer attribution must be designed and reviewed separately. The current Vulkan API observation limitation remains; actual GPU execution is still unavailable in this candidate.

## Approved M9 goal and execution order — 2026-10-25

Render at a lower internal resolution and use MetalFX Spatial to produce the protected 2128 × 1600 M4 output, aiming for comparable perceived visuals and lower total GPU/energy cost. A baseline-sized output alone does not prove equal detail. The scene input dimensions must be verified; final-image scaling may soften HUD/text, so evaluate scene-only upscale/native UI if accessible. Temporal remains separate until required motion/depth/jitter/history data is available.

Start M9-A input/output/ownership/synchronisation design alongside M3-A GPU timing and M2-A pipeline work. Publish design findings before major rendering edits. M9-B default-off prototype follows useful GPU evidence and safe interop; it need not wait for all M6–M8 research. Prototype acceptance includes the scaler's GPU/energy cost, p95/p99, image/motion/HUD/colour, latency and lifecycle, plus matched energy/temperature tests before adoption. Current support=true is capability evidence only; no scaler is integrated. See the master plan's current approved sequence for concrete gates and continuing M1/M4/M7 responsibilities.

## M3-A implementation follow-up

[GPU-BATCH-1](14-gpu-sampling-and-metalfx-inputs.md) implements an optional direct-queue discovery route omitted from the earlier interface review: vkGetMTLCommandQueueMVK can expose a legacy underlying queue for direct MoltenVK handles. A chained concrete-class factory adapter filters exact registered queues before attaching sampled completion handlers. It does not replace commit/present/encoding and leaves unrelated host queues unobserved, but interception is process-visible and requires LiveContainer correctness/overhead validation. Missing exports/factories/timestamps remain unavailable; no device result is inferred. The earlier discussion of current-interface limitations is historical; per-frame GPU attribution, watts and actual game upscaling are still absent.

M9-A source audit is complete for mapping the existing path and its requirements (R1/R2); actual lower scene input and a validated safe interop choice (R3/R4) remain open. The lower input -> MetalFX -> baseline output goal is preserved. See the batch guide for scene-versus-presentation alternatives and why no one-line swapchain reduction supplies the desired result.
