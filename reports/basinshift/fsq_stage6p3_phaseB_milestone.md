# FSQ Tokenizer (roadmap 6.3 / R8) — Phase B Milestone Report

Status: Phase B sweep COMPLETE. **HOLDING for the advisor gate. NOT sealed, NO pass declared,
NOT self-certified.** The R8 pass/fail and the config choice are the advisor's to approve.

CPU only. blind_force never loaded; holdouts (test_kgs, test_nlog, open-10) reserved and not used.
Frozen parquets/manifest untouched; no build_manifest/build_splits run. Outside the hashed set;
d5b35a00 untouched.

## 1. HEAD
`77b8432a1fcc259ed3585f4338d14f851c6bc428` at sweep time. This report + results are committed on
top; see section 6 for the new pushed HEAD (local == remote, GitHub-API-confirmed).

## 2. Pre-registration executed as LOCKED
patch 32; grid by level vector, TRUE codebook = product(levels); +2 pre-declared floor probes.
Standardization: TRAIN-global per-curve z-score in the baseline's stored space, std floor 1e-6.
Imputer: ONE global pool (kgs+nlog+force train), trained ONCE on RAW train, reused across all
configs (fixed raw_RMSE denominator). Degradation = that imputer on raw-dev vs
tokenized-reconstructed-dev, both scored through the committed `eval_harness` (same XGBoost
params/SEED/transforms as the committed baseline; scorer proven to reproduce the baseline 12/12
under the 6.3 env in Phase A). Scope: all 11 canonical curves as imputation targets. 30 epochs/config.

## 3. Results

### Raw arm (fixed across all configs — the degradation denominator; committed XGBoost on RAW dev)
| curve | raw_RMSE (physical) | dev n_samples | dev n_wells |
|------|------|------|------|
| GR   | 25.6842   | 5,487,809 | 559 |
| RHOB | 0.197557  | 2,994,770 | 483 |
| NPHI | 0.073298  | 1,189,400 | 273 |
| DTC  | 14.1003   | 3,266,374 | 319 |
| PEF  | 1.46538   | 510,985   | 125 |
| SP   | 65.0069   | 2,773,570 | 401 |
| CALI | 2.22710   | 2,659,658 | 453 |
| RDEP | 2031.99   | 2,832,967 | 422 |
| RMED | 988.186   | 2,329,153 | 350 |
| RSHA | 1563.96   | 640,414   | 112 |
| DTS  | 23.7425   | 27,164    | **3** |

No degenerate (near-zero / non-finite) raw_RMSE. **Caveat flagged (not silently passed):** DTS has
only **3 dev wells** (27,164 samples) meeting the >=100-valid threshold — its degradation is thin
and not robust (same class of thinness as the BasinShift Kansas-DTC n=9 caveat). It is reported
but should not be read as a stable per-curve result. RDEP/RMED/RSHA raw_RMSE are large in absolute
terms because resistivity is scored in physical ohm-m units (10**log10), which span decades;
degradation is relative so this does not distort the bar.

### Per-curve degradation % by config (codebook = product of levels)
| curve | cb64 [8,8] | cb125 [5,5,5] | cb240 [8,6,5] | cb1000 [8,5,5,5] | cb4375 [7,5,5,5,5] | cb15360 [8,8,8,6,5] |
|------|------|------|------|------|------|------|
| GR   |  9.81 | 10.98 |  8.40 |  8.01 |  8.05 |  7.72 |
| RHOB |  5.77 |  5.39 |  4.61 |  3.81 |  2.60 |  2.60 |
| NPHI |  8.78 |  7.31 |  4.67 |  2.84 |  3.46 |  2.25 |
| DTC  | 12.86 | 12.03 | 12.21 | 10.70 |  9.89 |  9.99 |
| PEF  | **19.46** | **19.02** | **19.76** | **20.49** | **20.42** | **20.09** |
| SP   |  0.73 |  0.34 |  0.48 |  0.12 |  0.02 |  0.24 |
| CALI |  0.70 |  0.30 |  1.80 |  0.79 |  0.69 |  0.58 |
| RDEP | 12.19 | 12.78 |  9.27 |  6.04 |  7.43 |  5.48 |
| RMED |  1.82 |  1.79 |  1.72 |  1.71 |  1.64 |  1.58 |
| RSHA |  0.48 |  0.46 |  0.44 |  0.42 |  0.42 |  0.40 |
| DTS* | 16.88 | 15.58 |  9.60 | 12.13 |  8.05 |  7.88 |
| **median** | 8.78 | 7.31 | **4.67** | **3.81** | **3.46** | **2.60** |
| **max**    | 19.46 | 19.02 | 19.76 | 20.49 | 20.42 | 20.09 |
| median <=5%? | no | no | **yes** | **yes** | **yes** | **yes** |
| max <=10%?   | no | no | no | no | no | no |
| **PASS bar (both)?** | **no** | **no** | **no** | **no** | **no** | **no** |

\* DTS = thin (3 dev wells), see caveat above.

### R8 bar (fixed: median <=5% AND no single canonical curve >10%)
**No config meets the bar.** The median half is met by the four largest codebooks (cb240 and up),
and median falls monotonically with codebook size (8.78% -> 2.60%). The max half is met by **none**
because **PEF degrades ~19-20% in every config and is essentially insensitive to codebook size**
(cb64 19.46% -> cb15360 20.09%). PEF is the sole >10% curve at the two largest codebooks; at
cb15360 every other curve is <=10% (DTC sits right on the line at 9.99%). That PEF does not improve
as reconstruction capacity grows 240-fold (cb64->cb15360, while RDEP more than halves 12.19%->5.48%
and DTC/NPHI/RHOB fall steadily) indicates PEF's failure is not a vocabulary-size limit but a
structural one (patch size / architecture / PEF's sensitivity as an imputation target to small
errors in its predictor curves). Surfaced for the advisor; the bar is unchanged and not relaxed.

## 4. Selection rule outcome (provisional, pending GATE APPROVED)
Rule: smallest true codebook among configs meeting the bar; tie-break median, then max, then fewer
dims; none pass -> escalate, bar unchanged. **Outcome: NO config meets the bar -> the rule selects
nothing and triggers the pre-registered ESCALATION to the advisor.** There is no provisional pick
to offer, because no config satisfies both halves of the bar. For the advisor's context only (NOT a
selection, NOT a bar relaxation): the smallest codebook meeting the median half is cb240; the lowest
overall degradation is cb15360 (median 2.60%, and PEF the lone >10% curve). Both fail max on PEF.

## 5. Cost vs estimate
Actual: total wall 8,304 s = **2.31 h**, ~**$1.01** at the A40 rate $0.44/hr. Per config ~1,250-1,338 s
(~21-22 min); prep (11 banks + 11 imputers + raw_RMSE) ~470 s, done once. Phase A estimate was
~2.0-2.9 h / ~$0.90-1.28 for a 4-6 config grid at 30 epochs; actual came in at the low end. **UNDER
both gate limits (<=$5 AND <=4 h); the running-projection guard never tripped.** Convergence: per-curve
train recon-MSE logged in `sweep_log.txt`; 30 epochs on millions of tiny 32-sample patches; losses
were not still visibly descending as in Stage 1's budget-bounded case, but a convergence sweep on
epochs was not pre-registered and is not claimed here.

## 6. Artifacts committed
- `scripts/basinshift/fsq_phaseB_sweep.py` — the sweep driver (banks+imputers built once, resumable
  per-config result files, 4 h projection guard, degenerate-curve handling, selection rule).
- `reports/basinshift/fsq_phaseB/fsq_phaseB_summary.json` — full per-config per-curve results +
  selection outcome + cost.
- `reports/basinshift/fsq_phaseB/raw_denominators.json` — the fixed raw_RMSE per curve.
- `reports/basinshift/fsq_phaseB/results/{cb64,cb125,cb240,cb1000,cb4375,cb15360}.json`.
- `reports/basinshift/fsq_phaseB/sweep_log.txt` — full run log.
- `docs/fsq_6p3_phaseB_env_2026-07-23.txt` — pip freeze snapshot.

## 7. HOLD
Holding for the advisor to rule the R8 gate on this evidence. No config passes the locked bar
(PEF ~20% in all), so the pre-registered outcome is ESCALATION. I am not sealing, not declaring a
pass, and not selecting a config. Awaiting the advisor's decision (e.g. accept the escalation and
direct next steps for PEF / patch size / architecture, or otherwise rule).
