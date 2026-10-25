# Required IPA handover contract

User requirement recorded 2026-10-25. Applies whenever Codex produces/delivers a new Husk IPA. Read [AGENTS.md](../../AGENTS.md) and the [master plan](../../PROJECT_PLAN.md) first. Preserve the baseline, remaining experiments and separate M4/Duo targets.

## Plan connection and identity

The user-facing delivery must state:

- Affected milestone/task/bug IDs, objective and observed problem.
- Sequence: prerequisite evidence -> what this IPA changes -> test/decision it enables -> next milestone. Explain why this build is useful now.
- Implemented changes versus demonstrated device/performance/energy benefits and remaining unknowns; name unchanged experimental defaults where needed to run the test correctly.
- Full source SHA and packaged identity (including an honest dirty suffix), workflow/check/build/package result, artifact link and checksum when available. Documentation-only follow-ups do not change the binary's source.

## Completion percentages with an explicit basis

Define a versioned, concrete acceptance checklist for the affected scope before scoring; record it in the build handover/master plan. Reuse existing milestone gates rather than redefining success to increase the score. Split broad gates into reviewable conditions when needed; keep stable IDs and explain any scope/denominator change.

Report three separate rows for each affected scope:

| Track | Required presentation |
| --- | --- |
| Implementation and build | Passed implementation/build gates / defined gates, percentage, evidence and remaining work |
| On-device correctness and relevant performance | Passed device gates / defined gates, percentage, named hardware/configuration and pending tests |
| Benefit/energy validation | Passed applicable benefit gates / defined gates, percentage of validation completed, measured result or explicitly unknown/inconclusive |

Example of format only, not Husk's current score: “M3-A implementation: 3/4 gates = 75%; device: 0/3 = 0%; energy benefit: unknown, 0/2 validation gates passed.” Partial or inconclusive gates are pending unless their checklist explicitly defines evidenced sub-gates. Unsupported data is unavailable, not a pass. Separate measured no-benefit results from validated savings; an experiment can finish with no benefit and be closed/reverted without representing an optimisation as successful.

These percentages describe checklist completion, not effort, time remaining, percentage battery improvement or percentage of maximum possible efficiency achieved. Give score changes from the previous handover when comparable. Every future IPA must additionally report a numeric **overall weighted permanent-plan completion percentage** under [HUSK-ROADMAP-v1](ROADMAP_PROGRESS.md), with its component breakdown, source/evidence date, model version and change since the prior comparable build. Use whole-milestone gate scores; the 100% implementation of a small increment must not become 100% of its parent milestone. State when the score is the first baseline or a rebaseline. Keep M4 delivery/validation separate from the future Duo; M10 has an explicit reserved weight. Define concrete gates for research decisions before scoring them. Always retain the affected-task track percentages and exact user instructions alongside the overall number.

## Consolidated delivery and minimal device testing

Complete a substantial, reviewable batch of feasible implementation and required automated checks before delivering another candidate. Reuse the existing telemetry; additional diagnostics need a named missing measurement/confirmed defect and a concrete decision they enable. Independent options may share one installation while preserving separate toggles/defaults/rollback and one behavioural change per comparison.

Analyse existing exports before requesting more gameplay. State the minimum capture duration, the particular uncertainty, the gates the result could inform, and why existing evidence cannot answer it. Reuse one capture across questions where its conditions support that analysis. Keep correctness smoke tests distinct from sustained energy comparisons.

Record the active source/artifact when the user starts testing. Keep that candidate's instructions stable and assess the returned files before asking for an update/repeat, unless a confirmed blocking correctness/measurement defect needs a replacement. Documentation-only updates must not manufacture another IPA or test request. Continue independent engineering without invalidating the active test.

Report implementation readiness separately from device/benefit acceptance and the fixed weighted overall score. Consolidation does not waive correctness checks, baseline preservation or measured-benefit requirements.

## Detailed user instructions required in the delivery message

Fill these with the actual build's controls and procedures; do not send the user an unfilled template or require them to infer steps from developer notes.

1. Explain the test's purpose and what decision their result will enable. State whether this is a quick correctness check, a focused diagnostic run or a sustained comparison; give the expected time and number/order of runs. Request only the current uncertainty's tests.
2. Provide installation/update and complete restart steps appropriate to their existing LiveContainer workflow. Preserve game data and compatible cache. Never request cache deletion for a cold test without an explicit safe backup/restoration procedure and authorised need. Identify baseline/candidate builds if comparing.
3. Give exact in-app menu paths, resolution/output/internal-input distinctions, graphics preset, FPS, worker/submission modes, and every relevant diagnostic/experimental toggle ON or OFF. Change one behavioural variable per comparison. Do not describe a capability-only MetalFX field as an enabled upscaler.
4. Specify unplugged/charging status, brightness, orientation/window mode, case/accessories, comparable starting/ambient temperature and scene/cache conditions. Separate charging and unplugged evidence. Ask only for equipment the user has; label optional Instruments/thermometer tasks external.
5. Specify the mission/menu/effect and action order, session start/stop, repeat/restart conditions and duration. Give phase markers and exclusions for manual interruptions/lifecycle actions. Retain excluded diagnostic context. Explain whether loading/first-use is included.
6. List observations to report: visible stutters, image/HUD quality, warmth, battery start/end/system indicator comparison, input/audio/lifecycle issues, and when/what action caused each event. Distinguish subjective warmth from temperature measurements.
7. Give exact stop/export/share menu steps for that IPA. Name required report.md, diagnostics.json, and attempt log only where needed, plus any specific screenshot or external capture. Ask for files from the same session/build and preserve identity. Avoid an unfocused request for another long log.
8. Explain expected success/failure signals and what the telemetry can establish. Include stop/restore conditions for crashes, blank/corrupt rendering, uncapped operation, serious pacing regression or thermal safeguards. State the exact safe default/toggle restoration.
9. Say what Codex will analyse on receipt, which plan gates it can close and the next engineering task. If no further user action is required, say so explicitly instead of inventing a test.

## Durable record and verification

Save each future build's filled handover and versioned checklist under docs/performance/builds/<source-sha>.md; identify successive artifacts separately if the same source is rebuilt. Link it from the master plan and evidence index. Record returned device evidence without retroactively attributing an older run to a new IPA. Update gate states and keep failed/inconclusive results. A release/build check never establishes on-device power savings.

The final delivery message must itself include a clear plan/progress explanation and actionable numbered device instructions. Links provide supporting detail; the user should not have to reconstruct their task across old messages. Documentation-only updates require diff/link/readback checks, not a new IPA or performance test.
