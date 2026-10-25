# M2 feedback/state investigation and M9 driver integration route

Scope: FEEDBACK-BATCH-3, checklist version 1, 2026-10-25. User authorises continued work without the iPad. Preserve the baseline; hardware/energy validation remains pending.

## M2 source finding

Reviewed bundled-version MoltenVK v1.4.2 MVKPipeline.mm and Layers/MVKExtensions.def. The driver advertises VK_EXT_pipeline_creation_feedback. Pipeline creation sets a valid pipeline-level feedback result, while shader-library lookup can set APPLICATION_PIPELINE_CACHE_HIT on shader-stage feedback. Husk's previous passive reader examined only the first pipeline-level result and could miss this separate stage evidence. A valid stage/library hit does not guarantee that Metal pipeline-state creation or other preparation is cheap. No absence of the pipeline-level hit bit establishes an expensive compile.

## Explicit diagnostic feedback request

New Game Graphics > Pipeline Creation Feedback (Diagnostic) defaults OFF, requires Pipeline Identification and a full restart, and activates only for exact Dungeons. When off, original device and pipeline arguments are forwarded unchanged. When on, startup checks the driver's actual extension list with bounded allocation; unsupported/missing query paths preserve the original device configuration. The extension is appended to a shallow copy only when advertised and not already requested. Guest queues/layers/features/flags/callbacks are retained. Only an added-extension VK_ERROR_EXTENSION_NOT_PRESENT permits fallback to the original request; device loss/OOM/other failures are not retried. Capability is invalidated on device destruction.

For up to 64 original pipeline infos per call, the helper copies top-level infos in original order and adds its own temporary feedback node only where no guest feedback node exists. All nested pointers, shader/state/compile flags, base-pipeline references and allocator/output pointers remain unchanged. Original chains remain linked after the new node and guest memory is not edited. Stage buffers match actual graphics stage count (1–16) or one compute stage. Unsupported sizes, unbounded chains and allocation failures forward original infos. Existing guest feedback is preserved, never duplicated. Copies/output storage survive the real API call and diagnostic read, then are freed. No Vulkan object is fabricated or deferred.

This diagnostic can add host work; collection/preparation overhead is separate from the timed original driver/cache-lock call. Extension/device/request counters and skipped/unsupported/declined paths are exported. No pipeline warming, compile-control flags, queue wait or changed default rendering behaviour is introduced.

## Separate evidence and partial-v2 grouping

Schema v5 retains prior fields and adds pipeline_feedback_request plus distinct valid/hit stage counters/masks and up to four shader stage/content-hash identifiers in first-pipeline-per-batch groups/events. Stage-feedback counts inconsistent with original stage counts remain unknown; masks map original stage indices, with identity mapping available only for sampled shader slots. Only VALID feedback is counted; invalid/absent feedback is unknown. Counts are since launch, not necessarily the included Efficiency Test span. Other batch pipelines are not represented by the first group's feedback summary. Driver feedback is neither energy nor exclusive frame/GPU execution time.

Partial-v2 identifiers add bounded vertex/binding, raster, multisample/sample-mask, depth/stencil, blend, viewport/scissor, tessellation and classic dynamic-state fields. Pointer values, opaque handles and padding are excluded. Ignored pointers for dynamic viewports/scissors, rasterizer discard and unsupported extended state are not dereferenced. Unknown extension/dynamic semantics stay incomplete. Render-pass/pipeline-layout compatibility and some extension state remain missing: these are still partial groups, not replay/cache keys. Versions must be retained when comparing exports; do not directly equate v1 and v2 hashes. Cache file format/compatibility keys are unchanged.

## M9 concrete insertion route from driver source

Reviewed MoltenVK v1.4.2 MVKSwapchain.mm, MVKImage.mm and MVKQueue.mm:

- initCAMetalLayer currently sets drawableSize from the guest swapchain _imageExtent.
- A non-headless MVKPresentableSwapchainImage gets its rendering MTLTexture directly from the drawable. There is currently no independent lower-resolution colour texture.
- MVKQueuePresentSurfaceSubmission::execute obtains a presentation command buffer and encodes the present wait-semaphores before calling presentCAMetalDrawable, then commits the buffer.
- presentCAMetalDrawable owns scheduled/presented/completion handlers, semaphore/fence signalling and resource retention. Those mechanisms must be preserved.

A **dedicated experimental driver integration** could keep an independently allocated low-resolution per-swapchain-image render texture, retain a baseline-sized drawable and encode MetalFX into that existing presentation command buffer after its render-completion waits and before presentation/commit. This is a concrete candidate location, not a validated implementation. It still needs device/queue-order verification, resource-state/usage/format/colour correctness and performance evidence.

Do not repurpose _mtlTextureHeadless for this: getCAMetalDrawable returns nil when that headless field exists, disabling ordinary presentation. A new input resource needs its own ownership, memory accounting/residency, image-view behaviour and lifetime handling. Acquisition/back-pressure currently happens through drawable access; moving it to a later upscale/present phase changes buffering/latency and must be assessed. Preserve fences, availability signalers, present IDs/modes and completion accounting, including pause/resize/device-loss and late callbacks.

The experimental path would need separate input/output extents and a user-controlled configuration. V4 would preserve the chosen experimental input size while the output remains 2128 × 1600; turning the experiment off must recover the current direct high-resolution path. Changing drawableSize alone cannot supply this. Input must permit shader reads/render-target use; output must meet the scaler's actual texture-usage requirements (do not assume framebufferOnly output works). Validate BGRA/transfer functions, SDR tone mapping and MetalFX colour processing. Create/cache the scaler per compatible configuration, not per frame. Full-image scaling includes HUD/text; scene-only/native-UI composition would need earlier engine hooks. Temporal still needs unavailable motion/depth/jitter/history inputs.

This route requires a separate pinned-driver build/patch identity and dedicated regression tests; the ordinary bundled framework is not changed in this batch. Useful M3 GPU evidence and a validated safe interop design remain prerequisites for adopting a prototype. No assumed savings, GPU limit or identical reconstructed detail is claimed. M9-A R3/R4 and game scaler integration stay open.

## Increment acceptance gates

| Scope | Implementation/build | Hardware/benefit |
| --- | --- | --- |
| M2 feedback increment | F1 explicit supported-extension/default-off negotiation and lifetime safety; F2 bounded immutable-info feedback requests with guest/failure fallback; F3 valid stage evidence and partial-v2 distinctions; F4 portable/Apple checks plus clean IPA | Actual capability/feedback on M4; first/repeat/restart and expensive-call correlation; acceptable diagnostic overhead; targeted fix and net energy benefit remain pending |
| M9 route investigation | P1 source-mapped low-input/present command-buffer candidate with dependency ordering; P2 ownership/headless/usage/lifecycle constraints documented | Useful input texture, actual synchronisation/quality/cost and game scaler are unverified |

No device test requested while the user lacks the iPad. Existing saved logs should be inspected first. Later a focused identification + feedback session can test cache evidence; it is diagnostic, not an energy baseline. Do not combine worker/submission/limiter changes or indiscriminate prewarming with it.

Sources: https://github.com/KhronosGroup/MoltenVK/blob/v1.4.2/MoltenVK/MoltenVK/GPUObjects/MVKPipeline.mm ; https://github.com/KhronosGroup/MoltenVK/blob/v1.4.2/MoltenVK/MoltenVK/Layers/MVKExtensions.def ; MVKSwapchain.mm, MVKImage.mm and MVKQueue.mm in the same version/directory. API support in source must still be confirmed in the actual bundled runtime.
