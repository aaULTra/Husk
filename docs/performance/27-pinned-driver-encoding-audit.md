# M8 pinned driver encoding/synchronisation audit

2026-10-26, source-only audit of MoltenVK1.4.2 at `db66022459ffb663aa2b50f6b018bc2e124f5edf`, the experimental driver's actual pin. Upstream latest stable independently reports the same version. This is not a representative Dungeons cost trace or an energy result; M8-I2/I3/I4/I5 device-dependent criteria remain pending.

The source already implements several commonly suggested improvements. Do not relabel them as missing or add a second competing cache without identifying residual work:

| Existing mechanism | Pinned source | Engineering implication |
| --- | --- | --- |
| Buffer pointer/offset cache; offset-only native update | `MVKCommandEncoderState.mm`, `bindBuffer`, lines188–203 | Unchanged bindings skip native setBuffer; changed offset alone uses setBufferOffset. A generic “cache bindings” patch would duplicate existing work. |
| Texture/sampler identity checks | Same file, `bindTexture`/`bindSampler`,lines240–258; live-check variants near489–522 | Existing equality/exists checks skip already-bound native resources. Their per-call overhead and any other uncovered path need a trace before choosing an intervention. |
| Dynamic vertex stride/offset comparison | Same file,`bindVertexBuffer`,lines213–236 | Cache state includes stride in its comparison; a new cache must preserve that semantic distinction. |
| Render-state dirty flags/pipeline transitions | `MVKCommandEncoderState.h` near359;`.mm` `changePipeline`near1090 | Static state is marked dirty as pipeline state changes. Blindly suppressing encoding risks stale native state. |
| Command-object/buffer pools and reset/reuse | `MVKCommandPool.mm` `allocateCommandBuffers`,`freeCommandBuffers`,`reset`,lines34–77 | Acquires/returns pooled buffers; command-type pools exist. “Add command-pool reuse” is not an unimplemented generic feature. Actual game reset/release patterns remain unknown. |
| Optional asynchronous encoding queue | `MVKQueue.mm` `initExecQueue`,near303 | Synchronous configuration controls CPU execution dispatch; synchronous submission is not proof every submit waits for GPU completion. Existing independent Async control can be benchmarked. |
| Explicit queue-idle wait | `MVKQueue.mm` `waitIdle`,lines150–164 | The located waitUntilCompleted belongs to the Vulkan queue-idle route. It is not evidence of an unconditional per-frame wait. Never remove the required idle semantics from a grep result. |
| Submission semaphore ordering and encoding overlap | `MVKQueue.mm` `commitActiveMTLCommandBuffer`,near512 | Native/emulated wait ordering, prefill and completion/resource lifetimes interact. Batch6 adds component/driver evidence; no simultaneous prefill/limit/scheduling changes. |

Audited source-file SHA256:

- `MVKCommandEncoderState.h`: `198d81e4f3f87486168b284c994687d195d5db2ca52f247201d0f16da484d007`
- `MVKCommandEncoderState.mm`: `94b679b9e3e65077ca6283b4b9fed586c0fc05d6bcfc14e2cc33b0f1505ee548`
- `MVKCommandPool.mm`: `555eee73066557a2ef5df3ba71ed6fa3ae7d1f525ddc902c6b2f8b339d367e05`
- `MVKQueue.mm`: `7a6228015634567e6fe7425f95358430e64022ca71946bbfc0cba566444d242e`

Read-only source links use the exact pin: [encoder state](https://github.com/KhronosGroup/MoltenVK/blob/db66022459ffb663aa2b50f6b018bc2e124f5edf/MoltenVK/MoltenVK/Commands/MVKCommandEncoderState.mm),[state header](https://github.com/KhronosGroup/MoltenVK/blob/db66022459ffb663aa2b50f6b018bc2e124f5edf/MoltenVK/MoltenVK/Commands/MVKCommandEncoderState.h),[command pool](https://github.com/KhronosGroup/MoltenVK/blob/db66022459ffb663aa2b50f6b018bc2e124f5edf/MoltenVK/MoltenVK/Commands/MVKCommandPool.mm),[queue](https://github.com/KhronosGroup/MoltenVK/blob/db66022459ffb663aa2b50f6b018bc2e124f5edf/MoltenVK/MoltenVK/GPUObjects/MVKQueue.mm).

Next action: use M3 CPU/GPU/driver/component evidence to select a costly path. If a representative trace identifies repeated argument preparation, bytes uploads, allocation, locks, live-resource checks or redundant transitions despite these existing caches, inspect that exact route and implement one isolated candidate with its lifetime/correctness tests. Lower caller wall time does not prove lower total work or energy. Keep all broader command encoding, render-pass/load-store/bandwidth, queue/buffering, JNI/futex and compatible-version investigations explicitly open.
