# AA-series items AM, AN, AO, AP: CPU-only recompute over v3 raw results (2026-07-27)

Pod migrated mid-session: `j1ushqzaj5ids9` (host ran out of GPU capacity) ->
`s2xdsrjui3xtj8`, network volume carried over intact, HEAD unaffected. All
work in this doc is CPU-only arithmetic over already-saved
`atce_ablation_v3_raw_results_2026-07-26.json` (149MB) plus a fresh,
byte-reproducible refit of the tokenizer for AO. No GPU, no retraining, no
new arms. Script: `scripts/atce/atce_v3_recompute.py`, full output:
`reports/basinshift/atce_ablation_v3/atce_v3_recompute_2026-07-27.json`
(sha256 `7bddeee1b006e605ff822fe5dcdbb32aa5d0dfe5b1129f5abffce02e68a31357`).

## AM: bias statistics recomputed from raw results

**The previously-reported `nphi_relative_bias_pct_vs_real_mean` column is
NOT (aggregate abs_bias mean) / overall_real_mean_nphi * 100.** Reading
`atce_ablation_v3.py` lines 630-636: it is `bootstrap_ci()` applied to a
pooled list of 40 (8 wells x 5 realizations) per-REALIZATION ratios, each
divided by **that well's own real NPHI mean**, not the single
`overall_real_mean_nphi=0.328` shown alongside it (which is a separate,
unweighted mean-of-per-well-means). A mean-of-ratios with per-well
denominators does not commute with a ratio-of-pooled-means, which is why
back-calculating `abs_bias.mean / 0.32809 * 100` never reproduced the
reported figure. Verified by reproducing the old estimator exactly from raw
results: it matches the committed summary JSON numbers to 4 decimal places
for all six arms (e.g. Arm A: reproduced -10.7536% vs committed
-10.753619501293466%).

**New estimator (ratio of pooled means)** gives a materially different
picture for some arms -- pooling every individual sample (not per-well
means) across all wells/realizations:

| Arm | Old (mean-of-ratios) | New (pooled-ratio) | Signed abs bias |
|---|---:|---:|---:|
| A | -10.75% | **-14.20%** | -0.0423 |
| B-linear | -19.08% | **-23.76%** | -0.0666 |
| B-abs | -8.13% | **-13.76%** | -0.0340 |
| B2 | -12.35% | **-11.27%** | -0.0448 |
| C | +9.85% | **+16.69%** | +0.0332 |
| D | -7.13% | **-11.58%** | -0.0311 |

Pooled real mean = 0.337309 (n=54,051 samples), pooled generated mean varies
by arm (n=270,255 = 54,051 x 5 realizations). B-abs shifts the most between
estimators (-8.13% -> -13.76%); C nearly doubles in magnitude (+9.85% ->
+16.69%). Both estimators are legitimate; they answer different questions
(per-well-weighted average vs. sample-weighted pooled average). The
manuscript should state which one it reports and why, explicitly.

**Per-well relative bias is extremely heterogeneous.** Range across the 8
wells, per arm, spans as much as -34% to +3% (Arm A). Well `16/1-6 A` is a
consistent outlier with large negative bias across nearly every arm. Full
per-well values are in the committed JSON.

## AN: well-level bootstrap intervals (N=10,000, seed=20260715)

Well-level (resample the 8 wells, not the 5 within-well realizations) gives
materially different significance conclusions than the per-realization
framing:

| Arm | NPHI bias mean | 95% CI | Excludes 0? |
|---|---:|---|---|
| A | -0.0423 | [-0.0815, -0.0114] | yes |
| B-linear | -0.0666 | [-0.0905, -0.0391] | yes |
| B-abs | -0.0340 | [-0.0681, -0.0011] | yes (barely) |
| B2 | -0.0448 | [-0.0792, -0.0215] | yes |
| **C** | +0.0332 | **[-0.0049, +0.0754]** | **no** |
| **D** | -0.0311 | **[-0.0682, +0.0051]** | **no** |

**Paired, matched-resampling differences** (same well-index draws used for
both arms in each resample):

| Comparison | NPHI bias diff | 95% CI | Significant? |
|---|---:|---|---|
| B2 - A | -0.0024 | [-0.0188, +0.0140] | no |
| **B-abs - A** | +0.0084 | **[-0.0064, +0.0223]** | **no** |
| **B-linear - B-abs** | -0.0326 | **[-0.0470, -0.0184]** | **yes** |
| C - A | +0.0755 | [+0.0215, +0.1312] | yes |

**Item V's core claim is robustly supported**: B-linear is significantly
worse than B-abs (the reference-frame defect is real). **But B-abs's
apparent improvement over the no-conditioning baseline A is NOT
statistically significant** with only 8 held-out wells -- the point estimate
favors B-abs, but the interval spans zero. This is the honest, load-bearing
caveat for how confidently the manuscript can claim absolute-depth
conditioning helps.

**Arm C's degenerate per-well bootstrap: cause and fix.** Confirmed
directly (`np.allclose` across all 5 stored realizations for a sample well
= True): Arm C generates at `temperature=0.0`
(`atce_ablation_v3.py:551`), making decoding pure argmax
(`atce_ablation_v3.py:284`), so with an identical prime and a deterministic
eval-mode model, all 5 stored "realizations" are the same rollout -- any
bootstrap resampling those 5 identical values is mathematically guaranteed
to be degenerate, independent of any bug in `bootstrap_ci()` itself. Fixed
by resampling across the 8 WELLS instead of the 5 identical realizations
(wells genuinely differ); Arm C's well-level CI above is confirmed
non-degenerate.

## AO: tokenizer reconstruction bias for NPHI -- the result that can move the paper's claim

Tokenizer refit exactly as `atce_ablation_v3.py` builds it (imported
functions, not reimplemented: `ref.load_98_train_wells`, `ref.well_curves`,
`ref.make_split`, same `SEED=20260715`, same `StandardScaler` +
`MiniBatchKMeans(n_clusters=1000, n_init=3, batch_size=4096)` on the 80
train wells, 628,916 samples). Depth/real arrays were validated against the
stored raw-results real arrays for all 8 test wells before trusting any
decile breakdown (`np.allclose`, all 8 wells matched).

**Overall NPHI reconstruction mean bias, pooled over 54,051 held-out
samples: +0.000924** (real mean 0.3373, reconstructed mean 0.3382). This is
**roughly 40-70x smaller** than the observed model-generation biases
(-0.031 to -0.067 across the depth-conditioned arms). **The tokenizer's own
round-trip reconstruction is essentially zero-mean; it is not the primary
source of the "generated NPHI runs low" pattern.** That pattern is a
genuine property of what the trained models predict, not primarily a
codebook-quantization artifact.

Two smaller, statistically real secondary effects:

1. **Depth-correlated reconstruction bias**: Pearson r=+0.1386 between
   residual and absolute depth (p=7.7e-230, n=54,051 -- the tiny p reflects
   large N more than large effect size). By-decile breakdown shows negative
   bias in shallow/mid depths (decile 2: -0.0078, decile 3: -0.0053) turning
   positive at greater depths (deciles 6-10: +0.003 to +0.007). Real but
   second-order relative to the model-level biases above.
2. **NPHI-quantile shrinkage** (classic vector-quantization behavior): low
   NPHI values reconstruct high (q1: +0.0135), high NPHI values reconstruct
   low (q10: -0.0161) -- extreme values pulled toward codebook cluster
   centers. Expected property of k-means quantization, not specific to
   depth.

**Bottom line for the manuscript**: the null/positive-result structure
observed across arms is predominantly a property of the trained
depth-conditioning models, not the tokenizer. The tokenizer does have a
small, real, depth-correlated reconstruction bias that should be disclosed
as a limitation, but it does not explain the magnitude of the reported
generation biases.

## AP: code audit (no computation, citations only)

**Arm D's mechanism, exactly as coded** (`atce_ablation_v3.py` lines
480-497): the Athy trend (`phi0=0.6052, lambda_m=4068.0`) is computed in
standardized NPHI units and subtracted from the NPHI feature of the
**training targets only**, for the 80 train wells, then re-tokenized to
produce `train_tok_resid`. `model_d` trains on these residualized tokens,
conditioned on the same per-well `dnorm` signal as B-linear (matches the
observed +512 parameter delta and the generation-time depth-signal range
identical to B-linear's). **At generation/scoring time, every arm including
D is primed with the same unmodified `token_seqs[w]` and decoded via
`kmeans_centers[token]` -> `scaler.inverse_transform()`, with no step
anywhere that adds the Athy trend back** (grepped the full file for
`athy`/`ATHY`: confined to lines 79-84 and 480-497; nothing in the
generation loop at 255-297 or scoring at 585-641). D residualizes training
targets only; the inverse transform is never applied before scoring. This
is a genuine, code-confirmed defect, not a guess. No attempt was made to
estimate a corrected number -- that would require a new recompute with an
addback step, out of scope for an audit. Recommendation: D's reported NPHI
bias should not be read as a fair evaluation of the "trend-residual" design
intent as currently scored.

**Resistivity units -- no actual conflict.** This script reads
`data/raw/force2020/train.csv` directly (line 100) and applies no log10
transform anywhere (zero occurrences of `log10` in the file). The "stored
as log10" record describes the separate frozen-corpus parquet pipeline
(KGS/NLOG/FORCE combined), not this ablation's direct FORCE CSV read.
Neither record is wrong; two different pipelines.

**Generation-cap grid spacing -- also not a bug.** `median_dz` (lines
335-337) is measured directly from this ablation's own 98-well FORCE data,
not the frozen corpus's declared 0.1524m constant. Measured value: 0.152
m/sample (`measured_depth_spacing_m: 0.15200000000004366` in the summary
JSON). `20000 x 0.152 = 3040.0m` exactly, matching the reported figure. The
"3048m" premise assumes the frozen-corpus constant applies here; it
doesn't -- this script measures its own spacing from FORCE's raw,
unresampled sample intervals.

## Environment

pip freeze snapshot committed:
`reports/basinshift/atce_ablation_v3/pip_freeze_recompute_2026-07-27.txt`.
Pod for this trip: `s2xdsrjui3xtj8` (numpy 1.26.3, scipy 1.16.3, pandas
2.2.3 -- explicitly re-pinned down from an initial 3.0.5 per instruction,
scikit-learn 1.9.0 installed fresh for this trip's tokenizer refit, torch
2.4.1+cu124 unused by this recompute but present from the base image).

