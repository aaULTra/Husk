# M2 / PIPE-01: partial pipeline identification and cache feedback

Sequence: M1 reliable collection -> M2 identify costly groups and supported cache evidence -> M3/M4 attribution -> M5 selective preparation only with full valid state and measured benefit. This feature does not precompile pipelines or establish lower power.

## Controls and scope

Game Graphics > Pipeline Identification (Diagnostic) defaults OFF and requires full restart. It records bounded shader/state metadata and first/repeated/slow-call events. Game Graphics > Pipeline Creation Feedback (Diagnostic) is a separate default-OFF option requiring identification and restart. Ordinary energy comparisons use both OFF, plus Driver Phase Profiling OFF. Shader-cache persistence remains enabled independently.

The feedback option activates only for exact Dungeons. It requests VK_EXT_pipeline_creation_feedback only when the actual driver advertises it, preserves an already requested extension, and does not enable unsupported features. Temporary copied top-level pipeline infos prepend a feedback node only where the guest did not already provide one. Guest nested state, chains, ordering, base references, flags, allocator and output pointers are preserved. Counts/stages/allocation/chain bounds and failures fall back to original requests. Only an added-extension -7 result permits original-device retry; device loss/OOM are not retried. Full contract and source finding: [feedback batch](16-pipeline-feedback-and-metalfx-route.md).

## Partial-v2 identity

The signature includes shader bytes, stage, entry/specialisation, flags/subpass and bounded vertex/input-assembly/tessellation/viewport/raster/multisample/depth/stencil/blend/classic dynamic fields. Opaque handles, pointers and padding are excluded. Ignored pointers for dynamic viewport/scissor, rasterizer discard, mesh input and unknown extension state are not blindly read. Unknown/truncated/unsupported/contended metadata remains incomplete. No complete Vulkan pipeline-layout/render-pass/extension compatibility identity is claimed; distinct full variants may share one group, and hashes can collide. Groups cannot reconstruct Vulkan objects or act as driver cache keys.

Export signature_version when comparing groups. Partial-v1 historical hashes cannot be equated with v2. First-pipeline shader-stage enum/content-hash metadata is sampled to four stages and exposes known/unknown modules without exporting shader code. Feedback masks use original stage indices; only indices with exported shader metadata can be directly mapped to those hashes. Device/module teardown invalidates metadata so recycled handles do not inherit shader identity.

Capacity remains 4,096 shader modules, 2,048 groups, 64 queued events, four signatures per batch and eight event logs per report call. Group summaries aggregate since game launch by first sampled signature in a batch; they can include startup/excluded periods. Host batch durations overlap across threads, and may include scheduling/lock delays. They are not individual pipeline GPU times or proof that a slow call blocked a displayed frame.

## Feedback interpretation

Read valid driver outputs whether guest-provided or explicitly requested. The first pipeline-level application-cache-hit flag and its stages' valid/hit flags are separate evidence. The MoltenVK v1.4.2 source can report shader-library reuse through stage feedback even while pipeline-level application-hit remains unset. Stage hits do not guarantee cheap Metal pipeline compilation or prove which persisted seed supplied the data. A valid-no-application-hit bit is not proof that all driver caches missed or an expensive compile occurred. Absent/invalid feedback is unknown. Unsupported stage counts or feedback counts inconsistent with the pipeline are not dereferenced as valid stage data.

Schema v5 includes pipeline_feedback_request capability/injection/skip provenance, partial-v2 per-group costs, sampled first-pipeline shader identities, latest valid/hit stage masks and cumulative stage-valid/hit counts. Other pipeline members in a batch are not fully represented by the first pipeline's feedback summary. No aggregate whole-pipeline cache-hit rate is invented. Accepted cache seeds and growing files remain mechanism evidence only.

## Deferred device procedure

The user currently has no iPad; no test is requested now. Inspect any already-exported diagnostics first. When a focused M2 run is needed, keep 2128 × 1600/Sharp Efficient/60/Balanced/Driver Default, enable identification and explicit feedback, restart, then collect first/repeated action and persisted-cache restart evidence using phase markers. Keep limiter/submission/worker changes separate. Export report.md + diagnostics.json before closing, with startup attempt log if accessible for restore/checkpoint evidence. Diagnostic overhead must be assessed separately; do not compare an instrumented session directly with uninstrumented energy results.

M2 remains partial until state coverage is sufficient for the expensive variants, real first/repeat/restart data and actual feedback support are established. M5 prewarming still needs complete valid creation state, noninteractive preparation, correctness and total-session energy checks. No indiscriminate warm-up is included.

History: earlier partial-v1/passive-only implementation and build evidence remain in EVIDENCE.md, DECISIONS.md and source-specific handovers. The explicit request and stage-aware reader supersede the old guide's claim that no extension/chain was ever added in diagnostic mode; default-OFF behaviour still preserves original requests.
