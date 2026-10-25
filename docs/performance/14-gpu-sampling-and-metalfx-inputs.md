# M3-A GPU sampling, M2 groups and M9-A integration audit

Scope/checklist version: GPU-BATCH-1, 2026-10-25. User authorises a substantial independently switchable batch to reduce installation/testing frequency. Sequence: corrected M1 -> M3-A actual GPU-buffer timing plus M2 group evidence -> M9-A input/output design -> gated M9-B rendering prototype. Existing M4 limiter and M7 scheduling comparisons remain separate.

## Concrete acceptance gates defined for this batch

| Scope | Implementation/build gates | Device gates | Benefit gates |
| --- | --- | --- | --- |
| M3-A GPU sampler | G1 known direct MoltenVK queue discovery with optional-export fallback; G2 opt-in scoped Metal factory interception preserving original calls; G3 bounded sampled timestamp collector with exclusions/session/loss/error handling; G4 schema-v3 raw records, explicit clocks and overlap-safe union; G5 executable portable/Apple adapter and Swift checks; G6 clean iOS build/IPA | D1 actual known M4 queue and valid GPU timestamps; D2 exclusions/restart/lifecycle correctness and stable graphics/input/audio; D3 representative CPU/GPU/host evidence interpretable without false per-frame/utilisation claims; D4 monitoring-off/on overhead measured | B1 measured instrumentation cost acceptable for diagnostic use; B2 GPU evidence supports or rejects a concrete optimisation hypothesis. Neither means power savings from instrumentation. |
| M2 group evidence increment | P1 colliding groups retain separate counts; P2 bounded structured since-launch counts/cost/valid-feedback export; P3 tests and iOS build | P-D1 first/repeat/restart groups observed; P-D2 actual supported feedback assessed and unknowns retained; P-D3 correlate slow groups with gameplay events | P-B1 subsequent targeted fix reduces relevant stalls; P-B2 net session/energy effect assessed. No prewarming or benefit yet. |
| M9-A design | R1 map current input/output/presentation path; R2 document formats/ownership/synchronisation/UI requirements and alternatives; R3 identify and verify useful lower-resolution scene input; R4 validate a safe full-output integration design | No game prototype available; runtime interop, visual and lifecycle tests pending | Total GPU including scaler and matched energy/temperature improvement pending |

Update each gate with evidence in the final source-specific build handover. Checklist percentages describe these concrete deliverables, not whole-project effort or energy saved. M9-A R1/R2 can pass from source audit; R3/R4 remain open. M9-B game upscaling is not implemented by this batch.

## M3-A implementation and safety boundaries

The direct bundled-driver path optionally resolves vkGetMTLCommandQueueMVK when intercepted vkGetDeviceQueue/vkGetDeviceQueue2 returns a queue. This legacy export is documented by MoltenVK for direct handles only; no Vulkan loader/layers are introduced, no extension or feature is silently enabled, and an absent export leaves timing unavailable. Device teardown removes exact-queue registrations before destroying the Vulkan device. Up to 16 registered queues are retained for their device lifetime.

The monitor's default-OFF “Sample game GPU execution (Diagnostic)” option installs a chained commandBufferWithDescriptor: factory adapter only on concrete classes of known game queues. Association with the exact queue filters out host/ANGLE/other queue work. The reviewed MoltenVK 1.4.2 factory uses this public selector. Class interception is process-visible; registration filtering is essential and must be validated on LiveContainer. A future driver using another factory may produce incomplete/no records. Up to eight concrete classes are supported; failures remain visible. No commit, present, encoder, priority or submission mode is changed. Once installed, the pass-through wrapper remains; with sampling off it adds only its inactive check, whose cost is not yet measured.

For one second every ten media-clock seconds, at most 256 newly created known-queue buffers get a completion handler. The handler reads GPUStartTime/GPUEndTime only after completion, records status and a separate completion timestamp, and never waits on reporting/GPU queues. A 1,024-record native ring and 16,384-record export cap bound memory; budget/capacity/contention loss and unresolved handlers are disclosed. The sampler adds no timer beyond existing session collection. It records only included spans; exclusion/stop/restart epochs reject crossing or stale completions. Earlier buffers, alternate factories, out-of-window execution and dropped/late work mean coverage is partial.

GPU values and sample bounds use CACurrentMediaTime's media clock; ordinary report event t uses tl_em_clock's separate monotonic origin. Both origins/field meanings are explicit. No mismatched guest presentation timestamps are reused. Invalid/zero/reversed/nonfinite/future GPU intervals are rejected. Completion-after-GPU-end is separate callback delay, not GPU execution. Swift clips intervals to sample bounds and unions overlaps across queues before reporting observed interval union seconds. Do not divide summed buffer durations by wall time and call the result utilisation; do not present this as GPU time per displayed frame. Device-wide power, per-frame attribution and physical temperature remain unavailable/external.

This is sampled instrumentation to guide work, not an energy optimisation. Use ordinary unprofiled runs for sustained energy comparisons and test overhead independently.

## M2 increment

The existing partial-v1 signatures remain partial: shader stages/entry/specialisation and selected state, without complete layout/render-pass/fixed-state identity. New open-addressed bounded group storage avoids losing occurrence tracking on a single hash-bucket collision. Schema-v3 exports since-game-launch first-group-per-batch counts, slow counts, aggregate/worst host duration and valid first-pipeline application-cache feedback counts. These host durations may overlap; incomplete identities can group distinct full variants. Valid-no-application-hit is not proof that all driver caches missed. No chain injection, replay state or prewarming is added. Identification still requires the saved default-off launch option and restart.

## M9-A source findings and integration decision

Current path:

1. TLUnityUIView creates a CAMetalLayer. Initial layout supplies launch dimensions; once UE4 launches, layout deliberately stops overriding drawableSize.
2. ANativeWindow exposes that same layer and selected dimensions. V4 intercepts UE4 resolution requests.
3. w_vkCreateAndroidSurfaceKHR passes that layer directly to MoltenVK. w_vkCreateSwapchainKHR observes the guest-selected extent; MoltenVK owns sizing/presentation.
4. UE4 requests r.ScreenPercentage=100, but acceptance/internal scene dimensions remain unverified. Present goes directly through the real driver plus the existing host cap; no separate MetalFX output pass exists.

Consequently, merely reducing the launch/swapchain extent reduces the current presentation extent too; it does not provide lower input plus baseline-sized output. The existing 1784 × 1336 run is not MetalFX. Optional legacy texture access exists in debug readback code, but that code waits the queue and cannot be reused for ordinary upscaling.

Two designs need evaluation after M3 data:

- Scene integration: locate a genuinely lower-resolution scene-colour output and upscale before native-resolution HUD composition. This best protects text, but requires UE4 render-target/pass hooks and actual CVar/texture verification; final-present access alone does not supply it.
- Presentation integration: keep guest rendering on a lower-resolution offscreen surface and own a separate 2128 × 1600 presenter/scaler. This requires correct acquire/submit/present semaphore ordering, queue/texture lifetimes across resize/pause/device loss, image-index ownership, usage/formats/colour handling and frame pacing. The whole HUD may be upscaled. A proxy swapchain/image mapping is a separate architectural change, not a safe one-line present hook.

Neither design is approved as implemented/safe simply from MetalFX capability=true. Do not change the protected direct presentation path in this diagnostic batch. Use measured GPU cost to choose a justified design and report findings before major rendering edits. M9 need not wait for every M6/M7/M8 experiment. Temporal requires motion/depth/jitter/history inputs not exposed here. The final target remains comparable perceived visuals at baseline output with lower total GPU/energy cost including the scaler.

## Reduced-frequency device collection

One installation can provide M3 and M2 evidence in two short diagnostic sessions: retain 2128 × 1600/Sharp Efficient/60/Balanced/Driver Default; identification ON at launch, GPU sampling ON in the test panel; limiter experiment/detailed profiling OFF. First session trigger/repeat the same chosen action; stop/export before a complete restart. Second session revisit the same action with persisted cache, again stop/export. Both are diagnostic runs, not energy-baseline comparisons. Build handover supplies exact steps/time/files. Leave M4/M7 behaviour unchanged during these sessions; defer further A/B requests until the files have been analysed.

Sources: MoltenVK v1.4.2 mvk_deprecated_api.h and MVKQueue.mm; current TLUnityView.swift, husk-tl-bionic-ndk.c, husk-tl-vulkan.m and husk-tl-ue4-graphics.c. Source review does not substitute for device validation.
