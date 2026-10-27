# Log-led continuation and official Husk audit — CONTINUATION-8

Sequence: archived E-M4-003–007 observations → M8 compatibility fixes and M2/M5 selective preparation → M4/M6 authoritative presentation-source discrimination → full Apple integration → later matched device/energy acceptance. User asks to use existing logs, complete feasible work without repeated installs, and adapt safe official Husk changes.

## Official source audit and selected adaptations

Official repository `Leviidev/Husk`, audited head `db6965a505488c4980dc19a891f2448b0dd409b5`; common base `2df074b3083ce2913922995f2f99249f1498b554`. Thirty upstream commits reviewed. [Commit-by-commit decisions](runs/UPSTREAM-2026-10-27.audit.json) retain exact SHAs and reopening reasons. This is a selective adaptation, not a wholesale merge or claim that this fork is official3.1.

- **Adapted f32163fa7c412c64ea5757c1613ca9a982ff4a4d:** a cached JNI miss must not permanently hide a native registered later; a successful lookup is refreshed after RegisterNatives generation changes. Unchanged successful lookup retains its cache. Actual upstream lookup/registration code tested against miss→register, replacement, late library export, cache hit and failed registration. Existing unrelated UnregisterNatives behavior is unchanged; no broader ART-completeness claim.
- **Adapted manifest-based selection from df76b76/385bd7f and audited official head:** inspect each APK manifest once; a confirmed base outranks filename heuristics, a confirmed split cannot masquerade as a base. Apply consistently to library load, import/scan and label/icon selection. Preserve readable fallback for unknown manifests and deterministic ordering. Eight upstream binary-manifest fixtures run on Apple. Existing single-APK Dungeons saves/settings are not migrated or deleted.
- **Local log-confirmed COMPAT-01 fix:** actual typed double `isnan`/`__isnan` and float `isnanf` bindings replace a logging stub for the unresolved symbol in libUE4 logs. Tests cover NaN, infinities, ±zero and finite/subnormal inputs through the real table entries. Correct classification is a compatibility fix, not proof that it caused earlier heat/stalls or that energy improved.
- **Retained separately:** broad launcher/accounts/localization; software-view geometry; battery guest metadata; compressed-heap reservations; Godot/V8 support; ZIP/OBB format rewrite; JIT/W^X/entitlements/installer changes. The supplied Dungeons APK/working LiveContainer configuration does not justify changing all these together. Low jetsam headroom alone cannot prove iOS terminated a process, so the upstream causal crash diagnosis is not copied. Changes remain in the audit with reasons; no investigated recommendation is silently discarded.

## M4/M6 display-timing provenance and full included aggregate

E-M4-007 native feedback has a20.83ms tail with host sleep disabled. Pinned MoltenVK substitutes its runtime clock when drawable `presentedTime` is zero, so existing rows cannot establish which times came from a real drawable report. This was an explicit attribution gap; re-reading the old JSON cannot recover the missing provenance.

An optional ABI1 observer now records the **existing** native `endPresentation` callback before that distinction is lost. Positive raw `CAMetalDrawable.presentedTime` and fallback estimates have separate fields/counters. There is no new callback registration, scheduling policy, drawable acquisition, readback or GPU wait. DefaultOFF adds only a relaxed enable check in this callback and a generation increment at swapchain construction. Original driver remains usable; missing observer exports are explicitly unavailable.

Only direct positive, increasing timestamps from the same swapchain generation and consecutive recorded callback attempts enter a0.1ms histogram. It accumulates throughout included capture even after its256-record raw tail overwrites. Long stalls retain exact worst/threshold counts; percentile in the >51.0ms overflow bucket is unavailable. Estimates, exclusions, late callbacks predating inclusion, generation changes, out-of-order times and try-lock losses break interval continuity. Exclusion changes use a fresh media-clock boundary; native callback recording never blocks on the diagnostic lock. Schema13 retains source, generation, losses, histogram and partial-coverage caveats. Offline audit reconciles histogram and raw-tail accounting; paired comparison flags changed display monitoring.

This is **partial measured drawable-report cadence**, not guaranteed full visible-frame throughput, pure GPU execution or a valid complete energy/frame denominator. OS callback delivery can omit/stall the latest presentations, and physical visibility is not independently observed. Monitoring overhead remains a device gate. It directly resolves source ambiguity in a future short capture; it does not retrospectively turn the old20.83ms tail into proof of a display bottleneck.

UI: Performance & Efficiency Diagnostics → **Sample native display presentation (Diagnostic)**. Requires the separate experimental driver, selected by MetalFX or Native Pipeline Cache **Driver Only**. OFF for clean energy comparisons. Keep source/configuration/driver identical between comparison sides; do not quietly add a driver change to the treatment. No new user capture is requested while implementation/build work is active.

## M5 bounded preparation prioritization and redundant-work avoidance

Existing logs show dozens of slow creations; keeping only the first eight complete native requests can fill the bounded queue before a more expensive later request arrives. The queue now retains at most the **eight highest observed native-call durations**, stable for ties, and prepares slowest first under the existing item/time limits. A later more expensive complete request replaces the cheapest retained request; lower-cost overflow is rejected. It never fabricates Vulkan state, guesses shader identities or increases the eight-request limit.

When optional FailOnBinaryArchiveMiss verification has already satisfied the Metal archive requirement for a slow call, that request is not captured again for extra preparation. Verification remainsOFF for normal comparisons; failure remains uncertain and uses the existing ordinary compilation fallback. Optional ABI1 priority counters expose eligible calls, replacements/rejections, known-satisfied skips and current observed cost range without changing archive ABI2. Complete copies/native ownership, device/generation guards, serialized bounded persistence, caller arguments/results, loading-cost receipt and original-driver rollback remain intact.

This mechanism removes a known redundant preparation opportunity and prioritizes the bounded budget. It is not semantic deduplication, a measured hitch/energy saving, or a solution to first-ever unknown state. Metal shader-library/front-end compilation can remain expensive even when native binary preparation succeeds. Include preparation/loading and monitoring in net energy acceptance.

## M5 stable compiler-compatibility namespace

The old native archive filename hashed the entire combined patch identity, including diagnostic-only code/scripts. A new diagnostic build therefore chose a different native archive even when the actual native shader compilation contract was unchanged. This is source-confirmed cross-build invalidation of the experimental native archive, not proof that it caused Vulkan-cache stalls in the supplied older logs.

Cache schema2 separates **compiler compatibility** from **full package provenance**. The stable key includes exact MoltenVK pin, pinned SPIRV-Cross revision, native compiler-contract revision, Metal archive format owner and, at runtime, actual Metal device name/registryID and OS version. The full combined patch digest remains in the manifest. Bump the compiler contract for MSL/native-descriptor compilation-semantic changes; diagnostic UI/observations do not by themselves invalidate the native archive. Metal still validates archive opening and actual function/descriptor lookup, with the existing ordinary compilation fallback. Old v1 files are retained, not silently trusted or migrated; the new namespace starts empty once. No Vulkan cache compatibility guard is weakened. Include this one-time cold condition in comparisons.

This preserves an opportunity for future cross-build native reuse without indiscriminate preparation. It does not prove a cache hit or lower heat/energy. No old archive or older successful shader is assumed usable just because its file exists.

## Checks and build sequence

Local source checks:348pass;17Apple-only checks pending (nine individual skipped checks plus eight binary-manifest cases in one skipped class),40suites. Actual Vulkan SDK31structures/96offsets passes. Driver transform accepts the exact pinned1.4.2 source; current combined patch identity is recorded with the final build manifest. Expected optional exports11, archiveABI2, display/priorityABI1. Changed native ownership/priority behavior must pass Apple tests, real driver compilation and full app/IPA packaging before a new candidate is ready.

Earlier source `d8fa46e82106a5c9940f70918e5ce82a934280ee` now passes Apple run40436887473/job121967599966:331checks,36suites,zero skips; SDK31/96,pinned driver,eight exports,app andIPA/upload. User reports Actions re-enabled; dispatch succeeds. Prior Actions-disabled error remains historical; underlying disablement reason is unknown. This proves that implementation's build readiness, not this continuation's changed source or physical benefit. Intermediate artifact12704853711 is parked; active0ff0758MetalFX test remains undisturbed.

## Persistent open work

All source/API/default-on claims remain separate from actual iPad correctness, visuals, pacing, cache reuse, monitoring overhead, strict Adaptive versus Balanced energy, preparation total cost, watts and surface-temperature acceptance. The new observer still needs on-device timing/overhead validation. No untested default is adopted.

Temporal MetalFX and live GPU-driven scene resolution still lack identified engine motion/depth/jitter/history/colour and safe setter/resource-lifetime contracts. No game libUE4/APK source/binary is available here to establish them; generic presentation scaling is not a substitute. Further trace-selected encoding/JNI/resource changes need a demonstrated remaining cost; actual Duo baseline/defaults require hardware. Those are unresolved dependencies, not implemented placeholders or abandoned investigations. Keep the complete M0–M10 inventory and unchanged weighted gates.


## Fixed score and implementation/build percentage

The resumed exact-source d8fa46e Apple331-check driver/app/IPA build completes unchanged M8-I3:an isolated sync/buffering candidate now exists with surface-checked2/3images,public native-buffer/prefill selectors,actual requested-versus-observed treatment exports and actual-code tests. This is scoped implementation acceptance,not measured overhead/pacing/energy acceptance. It adds0.42overall points under unchanged weights:28.67→29.09. M4-only32.32%,Duo0. Device/benefit tracks remain unchanged.

The existing weighted implementation/build checklist separately moves76.94→78.37%(+1.43percentage points):sum(M1–M10weight×passed-I fraction)/98;31/39unweighted I gates passed. M0 documentation excluded,Duo included. This is the defined existing checklist,not a claim that temporal/live-dynamic/trace-dependent research is implemented. scripts/roadmap_progress.py now emits this derived field automatically with unchanged overall scoring; its six checks and seven projection checks pass. No code count/test count is converted to energy or arbitrary progress.


Final source`5b7620237dc50906959e6a0aecf290f1e7ef6f11`passes365Applechecks/40suites/zero skips,Metal compiler probe,driver11exports/SDK31-96/app/IPA. [Handover](builds/5b7620237dc50906959e6a0aecf290f1e7ef6f11.md)/[receipt](builds/5b7620237dc50906959e6a0aecf290f1e7ef6f11.ci.json),independent package verification complete;candidate parked. Accepted overall29.09%,weighted existing implementation/build78.37%,M4-only32.32%,Duo0. No device/benefit gate added.
