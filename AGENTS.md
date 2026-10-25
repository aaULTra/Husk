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
- Report findings before major architectural changes. Do not bundle translation rewrites, MoltenVK upgrades, worker-policy changes or MetalFX into diagnostics work.

## Evidence and measurement rules

Working code, a passing build, a larger cache file, nominal thermal state and a 60 FPS cap do not prove efficiency. Do not mark Adaptive Trial complete until admission/application/rollback are validated and energy benefit versus Balanced is measured.

Label metrics MEASURED, ESTIMATED, UNAVAILABLE or EXTERNAL, with provenance, units and scope. Distinguish host present cadence from displayed frames; callback latency from GPU execution; cache seed acceptance from a cache hit; process CPU usage from device CPU utilisation; thermal classification from numerical temperature. Do not sum overlapping driver durations into frame time.

Use bounded diagnostics, event-driven collection and periodic aggregation. Do not add per-frame disk logs, queue-idle waits or synchronous GPU readbacks for ordinary monitoring. Keep heavyweight driver profiling opt-in and off for normal energy comparisons. Measure monitoring overhead.

Compare matched scenes, build/configuration, brightness, charging state, ambient/starting temperature and cache state. Separate first use, repeated use and persisted-cache restart tests. Record lifecycle/manual interruptions and exclusions without deleting diagnostic evidence. Do not infer power savings from lower resolution or lower CPU submission duration alone.

## Sequential plan traceability

For every task and substantive progress update, name its milestone/item ID, explain how it depends on prior work and which next milestone it enables. Include this sequence in the final handover and update the master plan. Do not report an isolated improvement without its place in the permanent roadmap.

## Coding, testing and handover

Use the existing architecture and tests. Preserve API arguments, results, object lifetimes and threading guarantees. Pipeline identification must not hash raw pointers/padding as stable identity or pretend incomplete state is complete. Unsupported feedback must remain unavailable. Never fabricate pipeline objects or precompile indiscriminately.

For code changes, run relevant portable checks and required regression suites; obtain a clean iOS build and IPA packaging before calling a device candidate ready. Record exact SHA, commands, results and environment limitations. A build validates compilation, not device performance. Documentation-only updates need link/status/diff checks, not an invented device result.

Before finishing each task, update PROJECT_PLAN.md and supporting records with changed implementation, tests/evidence, regressions, decisions, remaining uncertainties and next actions. Preserve unfinished, inconclusive and unsuccessful experiments. Never silently drop work when priorities change. A performance or energy claim requires evidence on the named device and conditions; otherwise leave validation pending.
