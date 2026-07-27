# Item O: pointer to embedded content (2026-07-27)

Per the AA-series brief item AE: item O's content (Arm B is rank-1 in depth;
B2's featurization; both reported whatever the outcome) was never committed
as a standalone decision doc. It is embedded directly in
`scripts/atce/atce_ablation_v3.py` and in the v3 summary JSON. This is a
pointer, not a rewrite.

## Where in the script

- Header docstring, lines 122-130: states Arm B-linear is "additive rank-1
  linear depth embedding on PER-WELL relative position, kept exactly as
  built per item O/V -- not silently fixed," and defines B2 as "richer depth
  featurization sharing B-abs's absolute reference frame."
- Lines 401-421: "item O BLOCKING PRE-CHECK" -- logs depth statistics as fed
  to B-linear's `Linear(1,256)` before training, confirming no scale-mismatch
  defect and reporting the reference-frame defect instead (per item V).
- Line 82, 126-132: Arm B2's multiscale sin/cos wavelength definition
  (log-spaced 10 m to 5000 m), the featurization O originally specified.
- Lines 434, 453: run-time log lines confirming B-linear "kept exactly as
  built" and B2 built per "item V amendment to item O's original B2 spec."

## Where in the summary JSON

`reports/basinshift/atce_ablation_v3/atce_ablation_v3_summary_2026-07-26.json`:
- `arm_blinear_param_delta_vs_a: 512`, `arm_b2_param_delta_vs_a: 3328` --
  reported regardless of outcome, per O's instruction.
- `arm_b2_feature_list` -- full 12-dim featurization list.
- `depth_scale_precheck` -- `scale_mismatch_defect_found: false`,
  `reference_frame_defect_found: true` (O's precheck result, refined by V).

## Ruling

O's content is adequately captured in the script and summary outputs. No
separate pre-registration doc is needed; this pointer satisfies the gap
noted in the Plan handoff (section 2, "four open gaps in the record").

