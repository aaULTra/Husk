# M3 external power, surface temperature and displayed-frame analysis

Sequence: M1 bounded session/export identity and exclusions → M3 external observation alignment → paired correctness/energy review → M5/M6/M7/M8/M9 adoption decisions. This tooling adds no gameplay collection or overhead. It does not establish that Instruments can attach to this LiveContainer installation; that remains a physical host/tool compatibility gate.

## What is implemented

`scripts/external_efficiency.py` consumes an existing Husk JSON export, a provenance manifest and normalized external CSV. It exports a concise Markdown report and structured JSON with SHA256 hashes of all inputs. It preserves unknown metrics, rejects mismatched session/build/device identity and unsupported quantities, and does not mutate input evidence. The template is deliberately incomplete: missing instruments, clock alignment or measurements cannot become a zero-power result.

Power is **EXTERNAL supplied whole-device system power in watts**. Integration, covered average and joules per displayed frame are **ESTIMATED calculations** from those observations. Instrument accuracy and supplied provenance remain unverified by this parser. CPU time, battery percentages, nominal thermal state and charging-cable input are never substituted for electrical power. Power analysis requires unplugged conditions; a charging/full UIKit sample inside included time contradicts and rejects an unplugged manifest. Surface-only analysis may record charging/full tests separately.

Surface readings are **EXTERNAL numerical measurements** at the named physical point. Sampled maximum and temperature above simultaneous ambient are calculated only where data exists. They are not chip/battery temperatures, and no surface interpolation or unsampled peak is invented.

Energy/frame remains **UNAVAILABLE** unless a complete, zero-drop, externally measured actually-displayed-frame timestamp stream covers the same power intervals. Requested 60 FPS, host cadence and estimated MoltenVK display feedback are not valid substitutes. Clock alignment still makes the denominator an estimate; do not imply precision beyond the instrument and alignment uncertainty.

## Capture and normalization contract

1. Preserve the exact `diagnostics.json`, original Instruments/raw power export, thermometer readings and any actual display-frame capture. Record instrument/software version, method, accuracy/calibration and raw source reference. Confirm that reported power is whole-device system power; USB-C charging supply power is a different quantity. Do not assume that an arbitrary device/OS supports Power Profiler.
2. Use supported Instruments tooling and wireless/unplugged profiling where supported. Record device/build identity, fixed scene/actions/cache condition, brightness, case/accessories, ambient and starting temperature. Keep profiling/charging conditions separate. No new physical capture is requested merely because this tool exists.
3. Normalize the original readings to UTF-8 CSV with exactly these columns and units:

   ```csv
   t_seconds,power_w,surface_c,ambient_c
   ```

   Each row needs a finite, strictly increasing timestamp in the external capture's seconds clock. Leave genuinely missing quantities blank. Watts are nonnegative; Celsius cannot be below absolute zero. Numeric rows must come from actual observations, not this document's examples. One consistent surface point per file/manifest; analyse different points separately.
4. Establish `Husk session t = external t_seconds + clock_offset_seconds`. Record the actual alignment method and a conservative nonnegative uncertainty bound covering the **entire capture**, including drift. A single guessed wall-clock start is insufficient. Choose `max_gap_seconds` from the actual sampling contract; the tool never bridges longer gaps or a missing power value. It never extrapolates before/after measured sample pairs.
5. The importer trims session edges by alignment uncertainty and expands each excluded interval by that uncertainty. It integrates linearly between adjacent valid power samples only inside remaining included intervals, reporting actual covered seconds and coverage fraction. Average watts are over covered intervals, not an assumed complete game session.
6. Optional displayed-frame CSV contains only `t_seconds`, in the **same external clock**. Its manifest declares instrument, method, raw reference, `quantity: actually_displayed_frames`, `complete: true`, `dropped_records: 0` and `coverage_seconds: [[start,end], ...]` in that clock. Unknown/partial coverage cannot establish energy/frame. Counting uses `(start,end]` for covered energy intervals; labels retain alignment/precision limits.

## Commands

From the repository root, generate a new manifest file from the actual session:

```sh
python3 scripts/external_efficiency.py diagnostics.json --template external-manifest.json
```

Fill every required provenance/condition/clock field from the real capture. Set `power` or `temperature` to `null` when that instrument/quantity was not collected, and leave its CSV cells blank. Do not leave an empty instrument object as evidence. The template's identity must match the supplied diagnostic exactly. Template generation refuses to overwrite an existing file.

```sh
python3 scripts/external_efficiency.py diagnostics.json \
  --manifest external-manifest.json --samples external-samples.csv \
  --output-prefix external-analysis
```

With a genuine complete displayed-frame stream, add `--displayed-frames displayed-frames.csv`. Outputs are `external-analysis.md` and `external-analysis.json`. Keep raw inputs beside them; output cannot overwrite an input. Inputs are bounded to32MiB each and500,000 CSV rows.

For an independently controlled existing recipe, attach both exact external analyses to the original paired-export preflight:

```sh
python3 scripts/compare_efficiency.py baseline/diagnostics.json candidate/diagnostics.json \
  --recipe spatial \
  --external-baseline baseline/external-analysis.json \
  --external-candidate candidate/external-analysis.json \
  --output paired-analysis.json
```

This retains the main identity/actual treatment/graphics/diagnostic/brightness/charging/pacing preflight. External analyses must hash those exact decoded diagnostic files and match their configuration. The external comparison requires at least99% included power coverage, comparable covered durations, the same measurement methods/surface point and matched recorded conditions. Different raw-source references are expected and allowed. A blocked main comparison remains blocked even if numerical power decreased. Descriptive watt/percentage/temperature differences award no roadmap gate.

## Acceptance and remaining dependencies

Use the same device and matched conditions; retain original sharp output, smoothness/input/audio/lifecycle and visual acceptance. Repeat important small effects at least three times, report spread and include loading/preparation/monitoring cost. Do not pool cold/warm or charging/unplugged runs. A single pair, manually asserted provenance, parser success or cooler subjective feedback cannot establish a precise energy saving.

The software arithmetic/provenance/CLI tests are synthetic, not measurements of an iPad. M3-I4 practical host capture, M3 device/energy gates and all option-specific energy gates remain pending until the actual tools/data support them. This completes the importer and comparison support; it does not fabricate an instrument, host attachment or calibrated physical reading.
