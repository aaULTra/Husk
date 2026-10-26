# M9/M1 quality, resolution evidence and bounded diagnostic work

QUALITY-BATCH-2, 2026-10-26. Prerequisite: E-M4-005, two active MetalFX sessions and corrected user feedback: probably the same visually, no issue noticed. No confirmed quality regression or energy benefit. User requests useful missing data alongside substantive implementation. Keep collection bounded and disclose overhead.

Sequence: prototype -> two-session evidence -> objective texture observations, selectable input budgets and collector fixes -> targeted quality/GPU/energy evidence. Preserve all shader/pacing/scheduling/device work.

Implementation/build gates Q1–Q5:

1. Q1 saved 80/85/90/95% MetalFX input controls; default 80 unchanged, all launch paths and metadata; selected output/default-OFF/baseline restoration retained.
2. Q2 separate direct texture observation API after validated encode; configuration versus observed fields and classified failures. No pixel readback/quality score or internal UE scene-resolution claim.
3. Q3 bounded hash inventory with reserved asset/target/area capacity, classified losses and probe counts. Asset dimensions cannot starve scene-area records. Off stays uninterposed.
4. Q4 media-clock exclusion brackets and end alignment; offline direct-marker preference with estimated anchor fallback and raw provenance. No GPU wait, queue or unbounded sampling.
5. Q5 executable portable/Apple checks, pinned driver build and app/IPA packaging.

Device gates D1–D3: observed sizes/controls/quality; useful target/area/direct-clock export; graphics/input/audio/lifecycle/rollback. Benefit B1–B2: matched monitoring overhead/work reduction and quality/GPU/energy. Compilation closes none of these. Higher input budgets are user choices, not measured optima. No change to worker/submission/limiter defaults or thermal safeguards; no driver upgrade, prewarming, temporal scaling or automatic quality cut.


Implementation details: aligned input at 2128 × 1600 output is 1696 × 1280 (80%), 1808 × 1360 (85%), 1912 × 1440 (90%) or 2016 × 1520 (95%). Percent controls dimensions, not pixel count or promised power savings. Scaler observes textures only once per image and validates each encode. The independent 64-byte observation ABI leaves existing 32/56-byte configuration/statistics ABIs intact; older drivers explicitly return unavailable observations.

Inventory snapshot counters are since activation; concurrent producers can advance observed/loss atomics across a snapshot. Target categories include colour/depth attachments and storage images, not proof of scene identity. Full assets cannot consume target/area quotas; saturated retained keys keep counting. Losses remain possible and disclosed.

Schema 7 adds direct exclusion brackets in the GPU media clock and a final alignment anchor. Offline analysis v3 prefers conservative direct start-before/end-after boundaries, reports total bracket uncertainty and observed end-minus-start offset change; it does not invent a drift-corrected exact GPU/display timeline. Old schemas 1–6 remain supported with labelled anchor estimates. Raw GPU rows are unchanged.

Required local regression run: 169 tests, 165 pass and four Apple-only checks deferred to IPA CI. Includes actual wrapper forwarding/default fallback/touch mapping, all input dimensions, optional ABI absence, inventory quota isolation/existing-key counts/probe bound/contention, direct exclusion preference without anchors, invalid boundaries, drift visibility and old device-export reconciliation. Final Apple validation passes all 169 checks, pinned driver compile/three custom export symbols and iOS app/package at 70de1bb9f27d99fa168ba583a306f8579d5115b4. No test instrumentation automatically enabled; no physical/energy credit.


Synthetic work check: [reproducible harness](runs/QUALITY-BATCH-2.inventory-benchmark.py), [five-repeat result](runs/QUALITY-BATCH-2.inventory-benchmark.json). Linux -O2, 500,000 saturated asset misses: old median process CPU 0.082556679 s; new 0.020580087 s. Different quotas are part of the change. Establishes reduced search work in this artificial workload only; no iPad gameplay, whole-process, GPU, energy or heat conclusion. No physical/benefit gate closes.

Observation dimensions/count reset when an accepted configuration changes with no live images. Classified failure counters, original encode/creation totals and hash inventory have their documented driver-load/activation scope; none are automatically a per-test energy metric.


Final Q1–Q5 implementation/build **5/5 (100%)**, new device D1–D3 **0/3 (0%)**, benefit B1–B2 **0/2 (0%)**. [Apple run 40291603363](https://github.com/aaULTra/Husk/actions/runs/40291603363) passed **169 checks**, separate pinned driver compilation and all three custom export checks, iOS app compilation and IPA packaging. [Download IPA artifact](https://github.com/aaULTra/Husk/actions/runs/40291603363/artifacts/12637221044); archive SHA256 `91b5c93cc48b590d979519608db9fc99210c86e9bae828115ed5990fafe71e0b`, expires 2026-11-02. Upstream MoltenVK 1.4.2 / `db66022459ffb663aa2b50f6b018bc2e124f5edf`; integration digest `7dfada085211e83ca1630ab8803f170f7caeb192ff4d85938fdf4f4d733b7e77`. Source and 21 changed files were verified against GitHub. Intermediate ac144ec4/run 40291412856 also passed, but use this final source/artifact with the report counter correction.
