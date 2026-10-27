# Husk standing engineering instructions

## Read before every task

Read this file and [PROJECT_PLAN.md](PROJECT_PLAN.md), then the linked evidence and decisions relevant to the task. Inspect the actual branch, HEAD and working changes before editing. The master plan is the source of truth for priorities and unresolved work; source code is the authority for what is implemented. Reconcile conflicts explicitly. Do not restart development or discard working improvements when switching tasks.

## Primary objective and protected baseline

Minimise practical battery energy, electrical power and unnecessary heat while maintaining excellent visuals, responsive gameplay and smooth sustained 60 FPS. Maximum uncapped FPS is not the principal benchmark.

The available test device is the 13-inch M4 iPad Pro, 1TB/16GB. Preserve the analysed code baseline `3c2d52c0f26ca9b40796633b169c40fd7f535e7c` and its 2128 × 1600 presentation reference: Dungeons V1.4, Sharp / Efficient, 60 FPS, Balanced, Driver Default, persistent cache enabled, detailed driver profiling off for normal comparisons, Low Power Mode off. This is the best documented working reference, not a proven energy optimum. The 1784 × 1336 run is a separate experiment, not a replacement default.

Preserve resolution V4 request/parser interception, cache compatibility and persistence safeguards, graphics/input/audio/lifecycle correctness and OS thermal safeguards. Never silently lower quality or replace requested 60 FPS with 45/30 FPS. Keep manual restoration available.

The future iPhone Duo needs its own real-device baseline, initially unfolded. Do not assume its specifications, optimal resolution, worker policy or submission settings from the iPad. Verify capabilities at runtime; use safe defaults on unknown devices.

## Before proposing an optimisation

- Identify the roadmap ID, objective, observed problem and mechanism of improvement.
- Check existing code, tests and decisions before adding functionality.
- Separate implementation, correctness, device performance and energy validation.
- Prefer removing confirmed unnecessary work before changing visual quality.
- Change one performance variable per comparison and keep experiments reversible.
- MetalFX goal: lower internal rendering resolution with the protected 2128 × 1600 M4 output and comparable perceived visuals. Prepare integration alongside M3 GPU investigation; the user explicitly authorised the default-off M9-SPATIAL-v1 prototype before physical GPU evidence. Preserve its separate experimental driver and original-driver rollback. Adoption/default activation still requires useful GPU evidence, verified interop, acceptable visuals and energy results; investigate independently of scheduling/driver experiments. Include scaler cost, HUD quality and measured energy in acceptance.
- Report findings before major architectural changes. Do not bundle translation rewrites, MoltenVK upgrades, worker-policy changes or MetalFX into diagnostics work.

## Evidence and measurement rules

Working code, a passing build, a larger cache file, nominal thermal state and a 60 FPS cap do not prove efficiency. Do not mark Adaptive Trial complete until admission/application/rollback are validated and energy benefit versus Balanced is measured.

Label metrics MEASURED, ESTIMATED, UNAVAILABLE or EXTERNAL, with provenance, units and scope. Distinguish host present cadence from displayed frames; callback latency from GPU execution; cache seed acceptance from a cache hit; process CPU usage from device CPU utilisation; thermal classification from numerical temperature. Do not sum overlapping driver durations into frame time.

Maximise actionable information alongside implementation batches, as requested by the user; prioritise missing decision-critical data and reuse existing collectors. Diagnostics have CPU/GPU/memory/energy cost: keep routine capture bounded, expose losses/coverage and make detailed or one-shot capture explicitly opt-in. Use bounded diagnostics, event-driven collection and periodic aggregation. Do not add per-frame disk logs, queue-idle waits or synchronous GPU readbacks for ordinary monitoring. Keep heavyweight driver profiling opt-in and off for normal energy comparisons. Measure monitoring overhead.

Compare matched scenes, build/configuration, brightness, charging state, ambient/starting temperature and cache state. Separate first use, repeated use and persisted-cache restart tests. Record lifecycle/manual interruptions and exclusions without deleting diagnostic evidence. Do not infer power savings from lower resolution or lower CPU submission duration alone.

## Sequential plan traceability

For every task and substantive progress update, name its milestone/item ID, explain how it depends on prior work and which next milestone it enables. Include this sequence in the final handover and update the master plan. Do not report an isolated improvement without its place in the permanent roadmap.

Structured diagnostics must include applicable plan IDs, subsystem, user-marked phase/context, observation time and outcome. Preserve unknown cause/phase explicitly. API success is a mechanism result, never automatic performance or energy acceptance. Separate observation/report timestamps from occurrence timestamps.

## Required handover for every new IPA

Every IPA delivered to the user must follow [the IPA handover contract](docs/performance/IPA_HANDOVER.md). Explain which permanent-plan IDs it advances, what prior evidence it uses, what changed, what remains unverified and the next milestone it enables. Supply the exact source/build identity, download link and check/build results.

Always give checklist-based completion percentages for the affected milestone/task, separating implementation/build, physical-device validation and benefit/energy validation. State passed/total gates, scope and checklist version; unknown or unmeasurable benefit stays unknown. Every future IPA must also include the overall weighted permanent-plan completion percentage, calculated using the fixed milestone weights and evidence rules in docs/performance/ROADMAP_PROGRESS.md. Show its change since the prior comparable build, the largest unfinished contributions and the scoring version. Never substitute a subtask score for a whole-milestone score or confuse progress with percentage energy saved. Keep the separately reported M4 and future Duo status explicit.

Provide detailed, build-specific numbered user instructions: installation/restart and cache preservation, exact menu/settings/toggles, controlled conditions, scene/actions/duration, phase/exclusion markers, stop/export/share steps, exact files and observations requested, pass/fail signals and rollback/stop conditions. Request only tests this IPA needs, specify what a returned result will decide, and state explicitly when no user testing is needed. Save the handover/progress checklist with the build evidence and update PROJECT_PLAN.md. The final user message must contain the actionable checklist, not merely a link to it.

## Delivery cadence and test economy — standing user requirement

Prefer substantial, reviewable implementation batches over repeated small diagnostic builds. Reuse existing diagnostics. Add instrumentation only for a named missing measurement or demonstrated collector defect, and state the decision it will resolve before implementing it. Complete feasible engineering and required automated checks before requesting another installation.

Independent experiments can share one IPA, but must retain separate controls, safe defaults and rollback. Keep one behavioural variable per controlled comparison; batching delivery does not permit mixing changes in a benchmark. Reuse the same capture for multiple questions when its configuration, phases and measurement coverage support them.

Analyse supplied/existing exports before asking for another run. Request the shortest session that resolves a specific remaining gate, with purpose, settings, duration, files and pass/fail/rollback steps. Avoid repeated general gameplay logs. Record the device build currently being tested; preserve its test instructions and analyse its results before requesting a replacement, unless a confirmed blocking correctness/measurement defect requires one. Continue independent engineering that does not invalidate that test.

Show implementation/build readiness separately from device and benefit validation and from the overall weighted score. Retain the fixed scoring model, acceptance standards, protected baseline, device separation and unfinished investigations. Faster delivery never means awarding unverified performance or energy credit.

## Conditional acceptance targets — standing user requirement

Prepare substantial consolidated candidates that can advance several existing milestones after successful testing. The user explicitly authorises a conditional50% target. Calculate conditional coverage from named unchanged gates, separately from actual evidence-gated completion; never award assumed performance/energy points. Use the retained VALIDATE-50-v1 scenario/campaign and projection tooling, not a fabricated “theoretical completion” score. Explain external equipment, unimplemented dependencies and failed/inconclusive results. An IPA's successful launch alone cannot pass the scenario. Reuse an already validated IPA when its runtime options cover the campaign; do not rebuild unchanged game code merely to give offline tools a new binary identity. Preserve the active test and analyse its results before requesting replacement tests.

When the user requests a minimum potential progress increment, map it to named existing gates and reproducible fixed-weight arithmetic before claiming coverage. Keep conditional coverage, actual earned credit and measured energy separate; do not weaken gates, assume equipment or turn a successful launch into all-gate acceptance. NATIVE-TEN-v1 records the current10.05point conditional scope; historical VALIDATE-50-v1 remains separate.

Review an optimisation end to end: configuration, added/removed hot-path work, translation/Metal behaviour, resource and threading lifetimes, persistence/rollback and exported evidence. Record the actual review scope and risks. Code review can establish a mechanism and catch defects; it cannot guarantee on-device energy or heat benefits. Include preparation/loading/monitoring overhead in net acceptance.

## Complete feasible implementation before repeated device requests

The user explicitly authorises completing the permanent plan's feasible engineering in substantial independent batches before testing later. Do not use missing physical validation as a blanket blocker for unrelated coding. Preserve the current test artifact/instructions, protected defaults and independent experiment controls. Implement concrete mechanisms and component-level diagnosis; do not add dummy toggles or claim unavailable engine inputs/hardware results exist. Record actual blocking dependencies and continue other feasible work. Implementation/build readiness and measured benefit remain separate under unchanged gates.

## Coding, testing and handover

Use the existing architecture and tests. Preserve API arguments, results, object lifetimes and threading guarantees. Pipeline identification must not hash raw pointers/padding as stable identity or pretend incomplete state is complete. Unsupported feedback must remain unavailable. Never fabricate pipeline objects or precompile indiscriminately.

For code changes, run relevant portable checks and required regression suites; obtain a clean iOS build and IPA packaging before calling a device candidate ready. Record exact SHA, commands, results and environment limitations. A build validates compilation, not device performance. Documentation-only updates need link/status/diff checks, not an invented device result.

Before finishing each task, update PROJECT_PLAN.md and supporting records with changed implementation, tests/evidence, regressions, decisions, remaining uncertainties and next actions. Preserve unfinished, inconclusive and unsuccessful experiments. Never silently drop work when priorities change. A performance or energy claim requires evidence on the named device and conditions; otherwise leave validation pending.


## Whole-plan code-completion requests

When the user requests100%implementation,work against the complete milestone inventory,not only a self-defined batch. Maintain each item as implemented/build-checked,feasible engineering still in progress,or genuinely input-dependent with the exact missing interface/data. Do not present a narrow10/10checklist as whole-plan completion. Missing physical benefit validation must not block independent coding; missing real engine inputs must not be fabricated. Continue useful independent work while CI runs,retain the user's active test and report remaining unimplemented code honestly.
