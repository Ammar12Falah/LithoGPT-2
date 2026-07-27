# Item V: pointer to embedded content (2026-07-27)

Per the AA-series brief item AE, and per Ammar's own framing: item V (the
dnorm defect) is **the most important defect found in the whole session**.
It was never committed as a standalone decision doc, but it is extensively
embedded in `scripts/atce/atce_ablation_v3.py`, the run log, and the v3
summary JSON -- not silently fixed. This is a pointer, not a rewrite, and it
exists specifically so this finding is not lost for lack of a dedicated file.

## The defect, stated once for the record

Depth entered the conditioned arms (originally, in v2/item O) as per-well
min-max fractional position (`dnorm`, range [0,1] within each well), not
absolute depth. The same normalized value therefore meant different real
depths in different wells (test wells span 340-2646 m), so a global
compaction trend (Athy's law) could not be fit or applied consistently
across the population using that feature. This is a units/reference-frame
defect that looks correct (bounded, normalized, no scale mismatch) but is
silently wrong in what it represents.

## Where in the script

- Header docstring, lines 6, 20, 140-148: full statement of the defect and
  the fix (Arm B-abs added; B2 amended to share B-abs's reference frame).
- Lines 377, 383: corpus-wide (not per-well) absolute-depth standardization
  computed from the 80 train wells only, logged explicitly.
- Line 422: "B-linear is kept exactly as built and reported as built, not
  silently fixed."
- Lines 513, 535, 572: `depth_signal_during_generation` tracking -- computed
  over the FULL well before generation-window slicing, per well/arm.
- Line 664: `depth_abs_standardization` note field.

## Where in the run log

`reports/basinshift/atce_ablation_v3/run_log.txt` logs, per arm, the actual
depth signal range seen during generation:
```
item V: [B-linear] depth signal range ... min=0.2404 max=1.0000
item V: [B-abs] depth signal range ... min=-1.2099 max=1.4006
item V: [B2] depth signal range ... min=-1.2099 max=1.4006
item V: [D] depth signal range ... min=0.2404 max=1.0000
```
Note D's range matches B-linear exactly (not B-abs/B2) -- confirming Arm D
shares B-linear's per-well relative-position mechanism, not the corpus-wide
absolute one.

## Where in the summary JSON

`atce_ablation_v3_summary_2026-07-26.json`:
- `depth_scale_precheck.reference_frame_defect_found: true`,
  `reference_frame_defect_note: "dnorm is position-within-well, not absolute
  depth; same normalized value means different real depths across wells"`.
- `depth_scale_precheck.scale_mismatch_defect_found: false` (the originally
  anticipated defect, per item O, was checked and NOT found; this is a
  different, unanticipated defect).
- `depth_abs_standardization`: `mean_m: 2501.46`, `std_m: 996.61`, computed
  from 80 train wells only.
- `depth_signal_during_generation`: per-arm min/max, matching the run log.

## What isolates what (both comparisons reported regardless of outcome)

- **B-linear vs B-abs** isolates the reference-frame defect alone (both use
  the identical rank-1 `Linear(1,256)` mechanism; only the input feature
  differs). Result (v3, NPHI abs bias): B-linear -0.0666 vs B-abs -0.0340 --
  B-abs shows a smaller absolute bias.
- **B-abs vs B2** isolates featurization richness alone (both share the
  corpus-wide absolute-depth reference frame). Result: B-abs -0.0340 vs B2
  -0.0448 on NPHI abs bias -- does not show a clean win for richer
  featurization on this metric alone.

## Ruling

V's finding is fully and repeatedly documented in the script, run log, and
summary JSON. This pointer exists to guarantee the finding is discoverable
from `docs/decisions/` even though no dedicated pre-registration file was
written at the time. No content is added beyond what the artifacts already
state.

