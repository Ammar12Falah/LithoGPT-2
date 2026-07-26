# Phase 7 / R9 -- physics prior implemented, fitted, validated (2026-07-26)

`src/lithogpt2/pipeline/trend.py` was a frozen interface with an unimplemented body
("SCHEDULED: weeks 3-4, handoff Section 5", commit `fa73c4a`, Week 1 scaffold, never
touched since). This implements `fit_athy_trend` and `carbonate_gate` against that
already-documented spec (bounds, thresholds, and gating conditions were already pinned
in the docstring and `configs/mnemonic_aliases.yaml`'s `prior_gate` block -- not invented
here).

## Implementation

- `fit_athy_trend`: phi(z) = phi0 * exp(-z/lambda) via `scipy.optimize.least_squares`,
  Huber loss (f_scale=0.03), bounds phi0 in [0.2, 0.7], lambda in [500, 5000] m (both
  already pinned in the frozen docstring).
- `density_from_porosity`: matrix/fluid mixing law, 2.65/1.0 g/cc (already pinned).
- `sonic_from_porosity`: Raymer-Hunt-Gardner-style transform (documented in the
  docstring as "a documented RHG-style transform" without giving the exact matrix/fluid
  endpoints; `dtc_matrix=55.5`, `dtc_fluid=189.0` us/ft are standard RHG literature
  values for sandstone matrix / fluid, used here as the concrete choice).
- `carbonate_gate`: three conditions per the docstring (PEF>=threshold on washout-clean
  samples; PEF-absent RHOB/GR heuristic sustained >=10m; post-fit residual z-score
  sustained >20m). **Interface note:** condition 3 needs a fitted `AthyTrend` to compute
  residuals against, which the original frozen positional signature (`well,
  washout_masks, config`) does not carry. Extended with an optional `fitted_trend=None`
  keyword -- existing 3-positional-arg callers still work (conditions 1-2 only); passing
  `fitted_trend` enables condition 3. This is a minimal, backward-compatible addition,
  not a silent break of the frozen interface.

Unit-tested on synthetic data before running on real wells: recovered phi0/lambda to
within 0.0024 / 7.0m of ground truth with 2% Gaussian noise plus 40 injected large
outliers (2000 samples), confirming the Huber-bounded fit is both accurate and robust.

## Fitted trends (frozen TRAIN wells only, per basin group, NPHI as porosity_like)

| Basin | n samples | phi0 | lambda_m |
|---|---|---|---|
| Kansas (kgs) | 11,179,487 | 0.3021 | 1691.5 |
| Netherlands (nlog) | 4,500,635 | 0.4166 | 3284.9 |
| Norway (force2020) | 763,350 | 0.6052 | 4068.0 |

All three are geologically plausible: Norway's shallower, less-compacted shelf section
shows the highest initial porosity and slowest decay; Kansas's mature Paleozoic section
(more diagenetic alteration, tighter carbonate cementation) shows the lowest initial
porosity and fastest decay; Netherlands sits between the two. Fit wall time 17.9s /
10.2s / 1.6s respectively (CPU only, negligible cost).

## Carbonate gate validation against FORCE 2020 lithofacies (98 frozen TRAIN wells)

Ground truth: FORCE_2020_LITHOFACIES_LITHOLOGY codes 70000 (Limestone), 70032 (Chalk),
74000 (Dolomite) -- all 12 codes present in the data cross-checked against the publicly
documented FORCE 2020 competition code table, confirmed exact match. Marl (80000) is
mixed clay-carbonate and is **excluded from the ground-truth carbonate set**, reported
separately rather than folded into precision/recall (a debatable inclusion either way;
excluding it avoids overstating the result).

blind_force was never loaded: the 10 blind_force well names were checked explicitly
against the loaded FORCE train.csv rows before scoring (`assert not ... & BLIND_NAMES`),
on top of the project's existing split-based exclusion.

| Metric | Value |
|---|---|
| Wells scored | 98 |
| TP | 40,133 |
| FP | 338,463 |
| TN | 730,198 |
| FN | 28,388 |
| **Precision** | **0.106** |
| **Recall** | **0.586** |
| Marl flag rate (excluded from GT, reported separately) | 0.443 (14,780/33,329) |

**Honest reading, not spun:** precision is low (10.6%) -- when the gate fires, it is
right about actual carbonate roughly 1 time in 9. Recall is moderate (58.6%) -- the gate
catches a majority of true carbonate intervals but at a real false-positive cost (the
gate flags a meaningful share of non-carbonate rock too, likely driven by the PEF
threshold and/or the RHOB/GR heuristic firing in tight cemented sandstones or other
high-density, low-GR intervals that are not carbonate). The docstring's own instruction
was to validate and report this number, not to hit a bar -- no precision/recall
threshold was pre-registered as a pass/fail gate for R9, so this is reported as a
finding, not a failure. The Marl flag rate (44.3%) is consistent with Marl's genuinely
mixed carbonate-clay composition and supports the choice to exclude it from ground
truth rather than count it either way.

## Artifacts

- `src/lithogpt2/pipeline/trend.py` -- implemented (was a stub).
- `scripts/r9/r9_physics_prior.py` -- driver: per-basin fit + FORCE validation.
- `reports/basinshift/r9_physics_prior_2026-07-26.json`, sha256
  `fc8c508f559e53294ca958176a4af68a35ad276890a706dcc26cfdf1f93cfd00` -- fitted trends,
  derived-transform samples, full validation confusion matrix, pinned bounds/thresholds.
- `docs/trend_r9_env_2026-07-26.txt` -- pip freeze, trend.py's own environment pin.

## Boundaries

This is R9's physics-prior fit and validation, reported per the frozen spec. It does
not select, seal, or gate anything on its own; whether/how the gate's precision/recall
should inform threshold tuning (the pinned 4.0/3.0 values were not tuned here, only
validated) is left for Plan/advisor review, consistent with "runs regardless of what
Phase 5 does" -- this phase reports facts, it does not rule.
