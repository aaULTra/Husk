# M7 / M9 / M1 — work while the iPad is unavailable

Scope: AUDIT-BATCH-2, checklist version 1, 2026-10-25. User explicitly asks to continue without access to the iPad. No new physical test result is assumed or requested now. Preserve all protected defaults and unfinished investigations.

Sequence: M3/M2 diagnostic candidate -> M7 verify requested versus observed worker treatment and M9 identify candidate image/area dimensions -> offline evidence audit -> separately justified scheduling or scaler experiment. This batch changes observation/reporting, not QoS policy, frame limit, resolution, submission mode or game upscaling.

## M7 source finding and implementation

Balanced keeps recognised normal TaskGraph workers at at-most Default, backgrounds at at-most Utility, and preserves critical/unknown roles. With the ten-CPU capacity hint, admitted Adaptive trials retain the first two indexed normal workers at Default and may cap later normal workers at Utility. This is a named-worker budget, not a P/E topology detector or job dependency classifier. Admission needs at least 20 seconds of qualifying windows (>=59 FPS, p95 <=20.5 ms, maximum <=50 ms, nominal thermal and bounded pipeline work). Prior approximately 57 FPS / 20.9 ms windows would not qualify; Balanced runs never request the extra caps. Selecting Adaptive alone does not prove an admitted or applied treatment.

New structured state separates selected/active policy, admission/rollback requests and successful setter calls. Up to 64 last self-observed thread records retain role/name, observer-local identity, timestamp, policy revision, before/after requested QoS, query/set errors and whether a policy change is retained. Records are historical last checkpoints, not live thread counts, instantaneous rollback, effective priority overrides, CPU time or core placement. Exited threads may remain. Unknown/failed queries export null after-QoS. Setter success counts alone do not prove the subsequent queried class or energy benefit.

Observation adds no new QoS setter call and changes no admission thresholds or rollback mechanism. Recording is bounded and try-lock-only; control snapshots use the controller lock off the render path. Activation is also locked against the new report reader. Controller snapshots every existing approximately two-second sample do not copy worker arrays; detailed last records are exported on stop. Diagnostic losses and failure counts remain visible even after the text-log cap. No P/E core pinning, cross-thread writes or dynamic worker count change is introduced.

CyPort's scheduling idea remains plausible, not established as the cause of Husk warmth. Relevant M7 device gates still need actual admission, worker self-applied changes, rollback and an independent matched energy/pacing comparison against Balanced.

## M9 render inventory

“Render Target Inventory (Diagnostic)” is default OFF in Game Graphics, saved compatibly and forwarded through fullscreen/window launch paths. It requires restart and activates only for the exact Dungeons project. When OFF, Vulkan lookup returns the original create-image/begin-render-pass functions, so ordinary rendering does not pass through the inventory wrappers.

When ON, wrappers preserve original arguments, results, outputs and command order. The observer groups successful VkImage creation's requested base width/height/depth/format/usage/sample fields and legacy vkCmdBeginRenderPass requested area dimensions/counts. A 256-group table bounds storage; try-lock/capacity losses are explicit. No texture readback, GPU wait, allocation substitution, size change or scaler pass is added. The render-pass function pointer is cached rather than resolved per pass.

This is partial requested state since launch, including loading/menus and potentially unused/discarded command buffers. It does not establish scene colour, HUD separation, executed pixels, actual internal 3D resolution, texture identity, render-pass dependencies or replay state. Swapchain-image creation, render-pass-v2/dynamic-rendering paths and extension overrides may be absent. Requested dimensions identify candidates for later investigation; they do not pass the actual scene-input gate or make MetalFX functional. M9-A R3/R4 and actual game integration remain open.

## Offline analysis and reproducible progress

Run `python3 scripts/analyse_efficiency.py diagnostics.json [second-diagnostics.json] --output analysis.json`. It supports schemas 1–4, audits window/summary arithmetic, GPU clipped interval union/coverage, selected versus admitted Adaptive and metadata differences. It reports descriptive differences and explicit uncertainty, never power/core residency or controlled benefit from matching metadata alone. Tests exercise actual E-M4-003/004 and malformed/overlap/condition cases.

Run `python3 scripts/roadmap_progress.py docs/performance/progress/roadmap-v1.json --output progress.json`. The ledger defines whole-milestone equal-weight gates within I/D/E tracks, using fixed milestone weights and 30/30/40 track weights. Passed gates require evidence. Missing milestones, unknown statuses, changed model weights or absent evidence are rejected. It separately reports overall, M4-only normalised and future Duo progress. Failed/unavailable device/energy work receives no credit. This is the first full ledger, not a re-interpretation of earlier narrow subtask 100% figures.

## Concrete acceptance checklist for this increment

| Scope | Implementation/build gates | Device gates | Benefit gates |
| --- | --- | --- | --- |
| M7 observations | W1 request/admission/rollback versus actual queried class and errors remain distinct; W2 bounded last-checkpoint export without extra QoS operations; W3 executable tests and clean iOS build/package | W-D1 real admitted trial plus worker changes; W-D2 delayed rollback/errors/role/lifecycle checked; W-D3 CPU/pacing comparison under matched conditions | W-E1 measured diagnostic overhead; W-E2 energy benefit of tested worker policy versus Balanced |
| M9 inventory | R1 exact-project/default-OFF lookup/settings/forwarding; R2 ABI-safe argument/result preservation and bounded nonblocking recording; R3 structured honest scope/export and clean Apple build | R-D1 real dimensions/groups observed; R-D2 no graphics/input/audio/lifecycle regression; R-D3 useful scene-input hypothesis independently validated | R-E1 diagnostic overhead acceptable; R-E2 later scaler's net GPU/energy/visual benefit |
| Analysis/progress tools | A1 archived/new-schema arithmetic and uncertainty checks; A2 fixed complete evidence-linked progress ledger; A3 executable tests in CI | No new hardware gate for pure offline arithmetic; runtime data quality remains M1/M3 | These tools do not claim energy savings |

Set final build/check evidence and gate scores in the source-specific handover after CI. The whole-plan ledger retains all M1–M10 gates; no on-device/energy gate passes from this batch. Device tests are deferred until the user has the iPad and any already-recorded GPU-BATCH-1 exports have been inspected. Do not ask the user to repeat old general gameplay now.
