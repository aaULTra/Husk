# Overall permanent-plan completion — HUSK-ROADMAP-v1

Standing user requirement, 2026-10-25: **every future IPA handover includes overall weighted permanent-plan completion**, in addition to task/track percentages, plan sequence and detailed user instructions. Source of truth: [PROJECT_PLAN.md](../../PROJECT_PLAN.md); enforcement: [AGENTS.md](../../AGENTS.md); delivery format: [IPA_HANDOVER.md](IPA_HANDOVER.md).

## Fixed milestone weights

| Milestone | Weight / 100 points | Reason |
| --- | ---: | --- |
| M0 durable plan/instructions/history | 2 | Essential continuity, small delivery scope |
| M1 trustworthy lightweight measurements | 12 | Foundation for all comparisons; correctness/overhead gates remain material |
| M2 pipeline identity/cache effectiveness | 10 | Directly observed severe hitch problem; diagnostics and actual reuse evidence |
| M3 GPU/power/temperature baseline | 18 | Largest remaining attribution gap and central evidence for energy decisions |
| M4 independent frame pacing | 6 | Focused existing reversible experiment with important smoothness acceptance |
| M5 selective pipeline preparation | 8 | Potential severe-stall remedy, substantial state/lifetime/net-energy requirements |
| M6 sizing/submission/buffering | 7 | Multiple presentation/synchronisation questions, benefits still uncertain |
| M7 Adaptive versus Balanced | 8 | Existing implementation; actual scheduling and energy comparison remain essential |
| M8 translation/encoding/JNI/futex/driver research | 7 | Broad profiling-led investigations; concrete decisions required before changes |
| M9 fixed/dynamic resolution and MetalFX | 12 | Major rendering/quality/synchronisation scope and potential pixel-work reduction |
| M10 independent Duo profiles/acceptance | 10 | Separate unavailable hardware; its own correctness, sustained efficiency and thermal evidence |
| **Total** | **100** | Stable denominator including both hardware targets |

These are explicit engineering planning weights based on objective relevance, scope, dependencies and uncertainty. They are not measured percentages of power consumption, predicted savings or estimates of exact remaining effort. Fixed weights prevent small UI/docs/code changes from dominating the overall number. M9 includes research, safe integration, visuals and measured net cost, not capability detection alone.

## Evidence-based milestone scores

For M1–M10, maintain three whole-milestone gate tracks:

- **I — implementation/build, 30%:** required design/implementation or justified investigation deliverables, relevant checks, clean iOS build/package where applicable. A narrow subtask can be implementation-complete while this parent track is partial.
- **D — device correctness/pacing, 30%:** actual relevant hardware, preserved image/input/audio/lifecycle behaviour, coverage/attribution and controlled frame-pacing evidence. Compilation and fake-queue tests do not pass these gates.
- **E — relevant benefit/energy evidence, 40%:** controlled evaluation of the milestone's intended effect with comparable conditions. For measurement milestones, this includes trustworthy representative baseline/attribution and instrumentation overhead, not an invented saving from logging. For optimisation milestones, include relevant performance/work and energy/thermal results. Adaptive's benefit remains unverified until measured against Balanced.

For each track define stable gate IDs, weights summing to 1 within that track (equal if not otherwise justified), pass conditions and evidence references. Set them before the next implementation/release assessment. Credit only passed gates; pending, partial without defined passed sub-gates, unavailable and inconclusive gates receive zero. A proven failure/no-benefit can complete a research decision gate, with the result explicitly recorded, but cannot pass a gate requiring an accepted improvement. Retain unmet objectives/reopening triggers; never relabel a rejected optimisation as energy-verified.

M0 uses its own documentation gates: permanent instructions/plan, evidence/history/test contracts and required handover discipline saved and reviewable. Its limited 2-point weight prevents paperwork from masquerading as efficiency progress.

For milestone m, with track fractions between 0 and 1:

`milestone_fraction[m] = 0.30 * I[m] + 0.30 * D[m] + 0.40 * E[m]`

`overall_percent = sum(milestone_weight[m] * milestone_fraction[m])`

Use the documented M0 documentation fraction in that sum. This produces a value from 0 to 100. Preserve full arithmetic internally; report an approximate whole percent to avoid false precision. Give underlying gate counts/weighted fractions and exact contributions in the linked ledger. A project's unknown physical efficiency ceiling is not a denominator.

## Ledger and reporting rules

Before the next IPA, initialise the complete gate ledger from actual code, evidence and acceptance standards in the master plan. Do not guess parent track scores from the last GPU-BATCH-1 subtask table. Store gate definitions/status/evidence and current milestone contributions in PROJECT_PLAN.md or a linked versioned progress snapshot. Every later build updates that same ledger and saves its snapshot under its source-specific build handover.

Every IPA delivery must state:

1. **Overall weighted permanent-plan completion: approximately N% (HUSK-ROADMAP-v1)**, and change from the last comparable snapshot, or first-baseline label.
2. Which milestones caused the change, their weights and passed gates; affected-task implementation/device/benefit percentages remain visible.
3. The largest unfinished contributions, evidence blockers and exact next user action.
4. M4 and Duo status separately. M10 stays unearned until its own documented gates pass; unavailable future hardware does not become not-applicable. An optional M4-only score must be separately labelled and normalised over M0–M9's 90 points, never substituted for the required overall figure.
5. Clear distinction between plan completion and measured energy reduction. Report energy savings only from comparative data; unknown remains unknown even if overall progress increases.

The overall score cannot reach 100 while mandatory implementation/device/benefit gates are open. If new evidence invalidates a pass, reduce the score and explain why. Never inflate progress by removing failed/unavailable gates or moving work to a new unweighted milestone.

Scope/weights can change only through an explicit documented roadmap revision with rationale, old/new breakdown and rebaseline. Retain earlier snapshots; do not present a denominator change as engineering progress. A device-specific no-benefit decision must retain the result and any still-open higher-level objective.

## Initial adoption

This requirement applies to all future IPA deliveries after the user's 2026-10-25 request. Existing build records keep their original scoped progress figures. This documentation-only update does not invent a current overall number, rebuild the IPA or require a user test; initial full-ledger scoring is mandatory before the next build handover. Report model version and evidence date so future tasks can reproduce and update the score.

## Reproducible ledger adopted

The initial whole-milestone gates now live in [progress/roadmap-v1.json](progress/roadmap-v1.json); run scripts/roadmap_progress.py to calculate exact contributions, overall, M4-only normalised and Duo scores. Tests reject missing milestones, changed weights and evidence-free passes. The first source-specific AUDIT-BATCH-2 snapshot establishes the scored baseline after Apple validation; its device/energy gates do not pass merely because the build succeeds. Keep later per-build snapshots immutable while updating the current ledger.
