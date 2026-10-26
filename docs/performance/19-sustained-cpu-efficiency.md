# Sustained CPU efficiency — EFFICIENCY-BATCH-3

2026-10-26. M7/M3/M6 sequence: E-M4-006 paired MetalFX logs -> remove the admission blocker for a separate controlled worker treatment and attribute actual CPU work -> matched pacing/work/energy acceptance. Preserve Balanced, strict Adaptive, selected output, 60 FPS, original driver/cache, thermal safeguards and every unfinished investigation. No forced P/E affinity or promised energy saving.

Evidence: report 3 = MetalFX ON, report 4 = OFF, same 70de1bb build. ON 55.628 host FPS and weighted process CPU75.47% of one CPU; OFF56.414 and61.76%. Unequal scenes/durations/cache/lifecycle and GPU export truncation prohibit causal improvement percentages. Observed actual scaler textures1696x1280 ->2128x1600, 48920 encode calls/no reported failure; target/area inventory now retains dominant lower-resolution HDR/depth/post-process dimensions. No measured electrical saving. ON battery25->10 in included samples gives a coarse64.28pp/hour; OFF stays10%, unresolved. Neither is a precise power comparison. User still notices warmth after >10 minutes.

Implementation gates C1–C5, fixed before coding:

1. C1 separate Baseline-Relative Trial (mode4), default Balanced unchanged. Existing strict Adaptive mode3 untouched in behaviour. Reserve fast-worker budget and all critical/unknown roles.
2. C2 collect >=20 seconds healthy starting cadence (>=55 FPS, p95<=21.5ms, max<=50ms, same existing cheap-pipeline/thermal/lifecycle guards). Admit only stable baseline (spread<=2 FPS); trial rollback on >2% FPS loss, >0.5ms p95 growth, six >22ms frames, >50ms frame, pipeline pressure, thermal/LPM/lifecycle; 60s cooldown. Requests remain distinct from self-applied observations.
3. C3 optional bounded CPU-thread snapshots and synchronous-submit thread CPU/wall attribution, with explicit missing/loss/clock/session scope. Default OFF; no per-frame file I/O or core-placement inference.
4. C4 preserve useful per-window GPU aggregates after raw export cap; bounded memory and disclosed raw losses rather than blindly expanding raw logs. Old schemas remain supported. Validate all supplied exports and archive provenance.
5. C5 actual tests, clean Apple app/driver build and IPA packaging; no physical acceptance from CI.

Device gates D1–D3: actual admission/application/rollback; trustworthy thread/submit/GPU aggregate export; correctness/lifecycle/quality/pacing against unchanged controls. Benefit E1–E2: reduced relevant measured CPU work without pacing loss and matched sustained energy/temperature evidence. All pending. Strict Adaptive versus Balanced energy remains open even if the new mode works. M4 engine-only and M6 async already exist and remain independent experiments; do not bundle them into worker comparisons. Electrical power and numerical temperature still require external tools.
