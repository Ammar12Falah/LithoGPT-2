# Item U: v1 tokenizer validation (BLOCKING) -- reverts to fresh refit (2026-07-26)

## Feature order: confirmed correct, no defect

Permutation search over all 24 orderings of {GR, RDEP, NPHI, RHOB}, matching each
permutation's empirical mean/std (from this ablation's own 80 train wells) against
v1's `scaler.mean_`/`scale_`, found the assumed order **[GR, RDEP, NPHI, RHOB]**
as the unique best match (sum-squared error 10837.9, next closest 10846.1 -- a
razor-thin margin over the next candidate, but still the minimum). The feature
order used throughout `atce_ablation_v2.py` is correct.

## Units: the log10-vs-raw-ohm-m concern is REFUTED for this pipeline

v1's kmeans cluster centers for the RDEP feature (unstandardized to v1's own
units) span **0.26 to 1983.6**, mean 12.79. A log10-transformed resistivity
feature cannot span into the thousands -- log10(1983) is ~3.3, not 1983. v1's
RDEP is raw ohm-m. This ablation's own `data/raw/force2020/train.csv` RDEP
column spans 0.046 to 1999.9 ohm-m (median 1.75, heavily right-skewed) -- also
raw ohm-m, matching. **No unit mismatch exists between v1's tokenizer and this
ablation's data path.** (The brief's warning about log10-stored resistivities
applies to the "kgs parquets" used elsewhere in the broader LithoGPT-2 project,
not to this ablation, which reads FORCE's raw competition CSV directly.)

## But a real distributional mismatch exists

| feature | v1 scaler mean / scale | this ablation's actual data mean / std |
|---------|------------------------|------------------------------------------|
| GR      | 74.22 / 32.64          | 75.68 / 33.85 (close)                     |
| RDEP    | 4.84 / 50.18           | 17.91 / 153.44 (mean 3.7x, std 3.1x off)  |
| NPHI    | 0.320 / 0.123          | 0.326 / 0.122 (close)                     |
| RHOB    | 2.341 / 0.221          | 2.343 / 0.225 (close)                     |

GR/NPHI/RHOB are close; RDEP is not -- v1's tokenizer was very likely fit on a
different well population, a different resistivity curve (e.g. RMED vs RDEP),
or with different outlier handling than this ablation's 98-well FORCE pool.

## Validation gate: v1 tokenizer vs a fresh refit on this ablation's own 80 train wells

| metric                          | v1 tokenizer (loaded) | fresh refit  |
|----------------------------------|------------------------|--------------|
| clusters used / 1000            | 998 (99.8%)            | 1000 (100%)  |
| cluster-usage entropy / 9.966 max| 9.629 (96.6%)          | 9.800 (98.3%)|
| tokenize->detokenize RMSE, GR    | 6.225                  | 3.928        |
| tokenize->detokenize RMSE, RDEP  | 9.923                  | 9.309        |
| tokenize->detokenize RMSE, NPHI  | **0.0403**             | **0.0136**   |
| tokenize->detokenize RMSE, RHOB  | 0.0454                 | 0.0254       |

Cluster usage and entropy are both fine for v1's tokenizer (not badly
underutilized) -- but reconstruction quality is materially worse on 3 of 4
features, and **NPHI -- this experiment's primary metric -- is 3x worse under
v1's tokenizer** (0.0403 vs 0.0136 RMSE). RHOB is ~79% worse, GR ~59% worse.
Only RDEP is comparable between the two.

## Ruling, per the pre-registered gate

"If v1's tokenizer is materially worse than a fresh fit... it is mismatched. In
that case REVERT to refitting for all arms and state the full-reimplementation
caveat in the outputs. Do not use a tokenizer you cannot validate. A validated
fresh fit beats an authentic one that is silently wrong."

A 3x RMSE penalty on the primary metric's own feature is material. **This
reverts item S's decision for the manuscript-candidate (final) run: all arms
use a tokenizer/scaler freshly refit on this ablation's own 80 train wells, not
v1's artifacts.** The caveat on Arm A returns to the fuller "reimplemented from
spec" (tokenizer included), not the narrower "v1's authentic tokenizer" framing
item S introduced.

Item S's finding is not erased -- it correctly and accurately described what the
exploratory v2 run (item W) did (loaded v1's artifacts) and that those artifacts
load cleanly. What changes here is the go-forward decision for the sealed run,
made only after actually validating the artifacts against real data, which item
S's brief did not yet require.
