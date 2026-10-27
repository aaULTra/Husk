# M1 → M2 → M5: native pipeline inspection feedback correction

2026-10-27. User reports pressing **Inspect captured native pipelines** produces no visible change. The active IPA identity and actual archive state have not been confirmed by an export. The latest offered consolidated candidate is `5b76202`; do not assume this UI report proves driver failure, cache misses or an empty pipeline list.

## Confirmed source defect and bounded correction

The existing screen inspects automatically on appearance. Pressing Inspect again assigns the same message when the sampled counters are unchanged. There is no visible acknowledgement, inspection time or action identity. Off, configuration failure and pending/failed native support are combined into one vague message. Preparation also has UI/context guards which silently return. These source defects explain why an action can look unresponsive; they do not establish the user's exact runtime archive state.

The correction adds:

- A numbered, UTC-stamped acknowledgement for every inspection, including repeated identical results in the same second. Inspect is explicitly described as a refresh button, not an enable switch.
- A host-only read-only inspection record: actual launch mode, configuration outcome, presence of all required driver APIs, snapshot validity and observed Vulkan-device lifetime. Driver ABI2/native compiler compatibility remain unchanged. No driver loading, compilation, GPU wait or cache write is triggered by inspection.
- Separate off, driver-only, not-configured, wrong-project, graphics-disabled, API-missing, rejected, device-ended, snapshot-unavailable, support-unconfirmed, empty, ready and preparing states. A failed snapshot is not reported as an empty capture. The current driver cannot distinguish a pending native support probe from a failed probe; that ambiguity is explicit rather than guessed.
- Explicit preparation-blocked messages and status when reservation fails, while retaining single-flight, pause/lifetime protections and bounded preparation.
- **Share archive inspection** exports a standalone JSON receipt even without a running/stopped test. It includes build/configuration/device/driver provenance, status, counts where available and observation time. Only the latest inspection is retained in memory; ordinary test JSON also includes it. Disk writes occur only on explicit export. Inspect does not enable capture or demonstrate reuse/energy savings.

V4/selected output, Sharp/Efficient, 60FPS, Balanced, DriverDefault, original/experimental driver choice, caches and user-selected MetalFX are preserved. No rendering/worker optimisation is added by this diagnostic fix.

## Verification and acceptance

Real C tests exercise launch modes, configuration rejection/missing APIs, accepted-but-unconfirmed support, empty/pending, snapshot failure, repeated side-effect-free inspections and teardown. The actual Foundation-only Swift policy is compiled/executed on required Apple CI; it checks distinct messages, same-second repeated acknowledgements, unavailable counters and every preparation guard. Required full iOS app/driver/IPA checks remain necessary before a replacement candidate is ready.

Current fixed scores remain **29.09% overall, 78.37% implementation/build**, M4-only32.32%, Duo0. No new roadmap acceptance/energy gate is awarded. M1/M2 diagnostic repair enables the next M5 preparation/restart decision; Adaptive/Balanced energy, actual GPU/power/temperature, pacing, encoding and all other unfinished experiments remain pending.

## Smallest device check after a corrected IPA passes packaging

Export any existing test before replacing/restarting it. Preserve saves and compatible caches. Launch with the same protected graphics/MetalFX settings and ArchiveEnabled, then open the diagnostics from the running game's bar. Tap Inspect twice. Expect a different inspection number each time, even when counts are unchanged. Tap **Share archive inspection** and send that one JSON. If support is unconfirmed/unsupported or pending0, stop there; no long gameplay repeat is requested. If ready, reuse the existing stopped-test/preparation/restart instructions. A success validates feedback/attribution, not cooling or cache-hit benefit. On rendering/input/audio problems, keep exports and restore the previous verified IPA/configuration; no data clearing is required.

Before a corrected IPA is ready, the current test exports remain useful. Do not ask the user to repeatedly press an apparently unchanged control or claim their current capture settings are wrong without the inspection evidence.

Local validation: all41required workflow suites passed on Linux;359reported checks,348passed and11explicit Apple/Swift skips. [Machine receipt](runs/NATIVE-INSPECTION-FIX.local-tests.json). Required Apple compile/native/full-app/IPA validation remains pending; local skips are not device passes.
