# 6.3 Diagnostic — Per-Basin PEF/DTC Addendum

Status: cheap completion of the advisor-ordered per-basin PEF check, extending it from distribution
(distribution shift, already reported) toward degradation. **HOLD; nothing sealed, ruled, or
carved. 6.4 stays gated.** Companion to `fsq_6p3_diagnostic_report.md`.

## What I ran, and what I did NOT (per Plan's gating condition)
Gate: run only if derivable from saved artifacts WITHOUT re-running reconstruction. The diagnostic
did NOT save per-well predictions or the tokenizer models, so the **per-basin DEGRADATION split**
(literal degradation of PEF/DTC on Kansas-dev vs Netherlands-dev, cb15360, both patches) would
require **retraining the cb15360 tokenizers (patch 32 ~22 min + patch 16 ~44 min) and
re-reconstructing dev** — i.e. re-running reconstruction. **Per the gate I did NOT run it.**
Estimated cost if authorized: **~70 min CPU, ~$0.5** (under the money gate), single run, no paid GPU.

What IS derivable without reconstruction, and which I ran (RAW arm only; `pef_dtc_perbasin.json`):
per-basin RAW imputation RMSE + well/sample counts for PEF and DTC; PEF TRAIN patch-bank composition
by source basin; dev well counts per basin. ~6 min CPU.

## 1-2. Per-basin RAW imputation (global imputer, per-basin eval) — raw_RMSE, wells, samples
The DEGRADATION column is intentionally blank (needs recon; not run). raw_RMSE here decomposes the
committed global-dev raw denominators (PEF 1.503, DTC 14.113) by dev basin.

| curve | dev basin | raw_RMSE | dev wells | dev samples | degradation (needs recon) |
|------|------|------|------|------|------|
| PEF | Kansas (kgs_dev)       | **0.6646** | 79  | 323,331   | not run |
| PEF | Netherlands (nlog_dev) | **2.3224** | 46  | 187,654   | not run |
| DTC | Kansas (kgs_dev)       | 10.2140 | 124 | 956,251   | not run |
| DTC | Netherlands (nlog_dev) | 15.4413 | 195 | 2,310,123 | not run |

Consistency: pooling these reproduces the committed global-dev raw_RMSE (PEF: sqrt of
sample-weighted mean of 0.6646^2 over 323k and 2.3224^2 over 188k = 1.503, matches).

**Finding: PEF raw imputation is 3.5x harder in the Netherlands (2.322) than in Kansas (0.665).**
The pooled PEF denominator (1.503) is a Kansas/Netherlands mix dominated by the intrinsically harder
Netherlands wells (consistent with the reported PEF cross-basin distribution shift: >6 tail 1.8%
Kansas vs 17.4% Netherlands). DTC is also harder in the Netherlands (15.44 vs 10.21) but only ~1.5x.

## 3. PEF TRAIN patch-bank composition by source basin (training-mix imbalance) + dev counts
| patch | Kansas | Netherlands | Norway | TOTAL | Kansas share |
|------|------|------|------|------|------|
| 32 | 147,325 | 33,718 | 20,394 | 201,437 | **73.1%** |
| 16 | 294,661 | 67,400 | 40,708 | 402,769 | **73.2%** |

PEF dev wells: Kansas 79 / Netherlands 46 (total 125, matches global-dev PEF). DTC dev wells:
Kansas 124 / Netherlands 195 (total 319).

**Finding: the PEF tokenizer's training signal is rare and Kansas-dominated.** PEF has only 201,437
patches at patch 32 (~2.4% of the 8.48M-patch total; among the rarest canonical curves, cf. GR
1.66M), and **73% of those patches are Kansas**, 17% Netherlands, 10% Norway. So the FSQ PEF
representation is optimized on the tight-band Kansas PEF and under-represents the heavier-tailed
Netherlands/Norway PEF.

## 4. Imputer hyperparameters/seed — identical across literal and matched arms (from code)
Both arms build `XGBRegressor(**eval_harness.XGB)` with **n_estimators=400, max_depth=6,
learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, tree_method="hist",
random_state=20260715, n_jobs=32**, and assemble training rows via `build_train_pool` with
**TRAIN_CAP=1,000,000, rng seed=20260715**. The literal arm reuses the raw-trained imputer; the
matched arm retrains with the **identical** params/seed/cap on reconstructed features (target stays
raw). The ONLY difference between the arms is raw vs reconstructed training features. Confirmed in
`scripts/basinshift/fsq_diag.py` (`precompute_global`, `precompute_raw`, `run_config`).

## 5. Matched-vs-literal for DTC/RHOB/NPHI across all 6 direction x config cells
Already in the committed diagnostic report section 6 (cross-basin tables + symmetry block). Restated
here (degradation %; matched_worse = matched worse than literal):

| direction | config | DTC lit | DTC mat | RHOB lit | RHOB mat | NPHI lit | NPHI mat | any matched_worse? |
|------|------|------|------|------|------|------|------|------|
| KGS->NLOG | cb4375 p32  | -0.84 | +0.32 | -1.48 | +6.29  | +0.70 | -0.89 | yes (DTC,RHOB) |
| KGS->NLOG | cb15360 p32 | -0.40 | +0.96 | +0.41 | +12.77 | +0.06 | -1.03 | yes (DTC,RHOB) |
| KGS->NLOG | cb15360 p16 | -0.61 | +1.48 | -0.52 | +9.27  | +0.25 | -4.06 | yes (DTC,RHOB) |
| NLOG->KGS | cb4375 p32  | +1.83 | -5.39 | +0.36 | +0.61  | -0.68 | +14.45| yes (RHOB,NPHI) |
| NLOG->KGS | cb15360 p32 | +0.84 | -2.36 | +0.35 | +1.12  | -0.34 | +17.48| yes (RHOB,NPHI) |
| NLOG->KGS | cb15360 p16 | +0.57 | -3.51 | +0.13 | +0.66  | -0.13 | -2.77 | yes (RHOB) |

Symmetry guard VIOLATED in all 6 cells (already reported). Largest matched blow-ups on headline
curves: RHOB +12.77% (cb15360 p32 KGS->NLOG), NPHI +17.48% (cb15360 p32 NLOG->KGS).

## Interpretation (REPORT, not a ruling)
The cheap evidence sharpens the intrinsic-vs-artifact question but does not settle it: PEF is **rare
(201k patches) and its training mix is 73% Kansas**, and PEF raw imputation is **3.5x harder in the
Netherlands than Kansas**. So PEF's failure has a substantial **rarity + training-mix-imbalance +
cross-basin-heterogeneity** component — the advisor's stated test for whether a carve-out would be a
finding vs a concession. What the cheap arm CANNOT resolve is whether the tokenizer degrades PEF
uniformly (intrinsic un-tokenizability) or disproportionately in one basin (an artifact potentially
addressable by rebalancing PEF training patches or more Netherlands/Norway PEF) — that is exactly
the per-basin DEGRADATION split, which needs the ~70 min reconstruction above. Pod holds for the
advisor to decide whether that run is worth it, and to rule the branch/gate.

## HEAD / artifacts
Committed on top of the diagnostic HEAD; see commit for the new HEAD (local == remote). Artifacts:
`scripts/basinshift/pef_dtc_perbasin.py`, `reports/basinshift/fsq_diag/pef_dtc_perbasin.json`, this
addendum. Nothing sealed; no branch ruled; no carve-out; holdouts reserved; blind_force never loaded.
