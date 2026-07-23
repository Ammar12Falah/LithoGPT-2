# 6.3 (R8) Diagnostic Round — Milestone Report

Status: diagnostic COMPLETE. **HOLDING for the advisor gate. Nothing sealed, no branch ruled, no
carve-out, R8 not self-certified.** Pod reports which branch the data indicates; the advisor rules.

Pre-registration (ruling verbatim + metrics/patches/basin-config/outcome-tree) was committed BEFORE
any compute at `docs/decisions/6p3_gate_ruling_e1029b20.md`, commit `93aad272`. This round adds an
appended ERRATUM (Part C) correcting a basin mislabel; see section 2.

Frozen splits (d5b35a00) untouched; holdouts (test_kgs, test_nlog, open-10) reserved and not used;
blind_force NEVER loaded. Outside the hashed set.

## 1. HEAD and cost
- Ruling committed at `93aad272` (before compute). This report + artifacts committed on top; see
  section 9 for the new pushed HEAD (local == remote, GitHub-API-confirmed).
- Diagnostic: 3 configs, wall 9,027 s = **2.51 h**, ~**$1.1** at $0.44/hr. **UNDER the money gate
  (<=$5 AND <=4 h).** Projection guard never tripped. CPU only, no paid GPU.
- Scorer re-proven under the 6.3 env before any degradation number: committed `eval_harness.py`
  reproduces the XGBoost baseline 12/12 ALL PASS.

## 2. ERRATUM (basin mislabel) — READ FIRST
`nlog` is the **Netherlands**, not Norway. **Norway is FORCE2020.** The committed pre-registration
Part B.3 mislabeled `nlog_dev` as "Norway"; the experiment is correct (`kgs_train->nlog_dev` and
`nlog_train->kgs_dev` = **Kansas <-> Netherlands**), only the prose label was wrong. Erratum appended
to the decisions doc with stated cause; original text unchanged.

**Consequence (prominent, not a config-line footnote): the cross-basin transfer testable on DEV is
Kansas <-> Netherlands ONLY. Kansas <-> Norway is NOT testable on dev, because FORCE (Norway) has no
dev split.** Norway exists as an eval basin only via the **open-10 holdout**. Using it is presented
as an OPTION for the advisor, with the reason to decline: open-10 is a reported BasinShift eval set,
so selecting the tokenizer on it would be selection on a test set (Plan recommends against; Pod does
not use it). The advisor's stated concern named Norway; the honesty test actually run is the
Kansas<->Netherlands proxy.

## 3. GLOBAL-DEV LITERAL (Phase B setup = the strict floor; defines outcome-tree branch 1)
Global imputer (raw, kgs+nlog+force train), scored on global dev (kgs_dev+nlog_dev), features
reconstructed. Degradation % per curve; raw_RMSE is the fixed denominator.

| curve | raw_RMSE | n_samp | wells | cb4375 p32 | cb15360 p32 | cb15360 p16 |
|------|------|------|------|------|------|------|
| GR   | 25.684 | 5,487,809 | 559 |  +8.05 |  +7.72 |  +6.32 |
| RHOB | 0.19701 | 2,994,770 | 483 |  +3.04 |  +2.96 |  +1.39 |
| NPHI | 0.073964 | 1,189,400 | 273 |  +2.35 |  +1.09 |  -0.67 |
| DTC  | 14.1129 | 3,266,374 | 319 | +10.30 | +10.26 |  **+9.20** |
| PEF  | 1.50338 | 510,985 | 125 | **+13.65** | **+14.83** | **+13.84** |
| SP   | 65.297 | 2,773,570 | 401 |  -0.24 |  -0.06 |  -0.41 |
| CALI | 2.2358 | 2,659,658 | 453 |  +0.87 |  +0.60 |  +0.81 |
| RDEP | 2086.3 | 2,832,967 | 422 |  +6.75 |  +5.18 |  +2.58 |
| RMED | 991.83 | 2,329,153 | 350 |  +1.23 |  +1.16 |  +1.05 |
| RSHA | 1562.9 | 640,414 | 112 |  +0.46 |  +0.43 |  +0.40 |
| DTS* | 23.742 | 27,164 | **3** |  +8.05 |  +7.88 |  +3.95 |
| **median** | | | | +3.04 | +2.96 | **+1.39** |
| **max**    | | | | +13.65 | +14.83 | +13.84 |
| median <=5%? | | | | yes | yes | **yes** |
| max <=10%?   | | | | no (PEF) | no (PEF) | **no (PEF)** |

\* DTS non-robust: 3 dev wells. Labeled non-robust; gates nothing.

Reading: **PEF is the sole curve above 10% under the literal floor at every config, including
patch 16 (+13.84%).** Patch 16 does NOT clear PEF. DTC improves to +9.20% at patch 16 (see §5).
So **branch 1 (clean literal pass on all canonical curves) is NOT met** — PEF fails the floor at
both patches.

## 4. STABILITY PROBE — cb15360 p32 re-run vs Phase B committed (DTC and PEF)
The re-run's global imputer uses a fresh-seed 1M subsample (Phase B used the harness's shared rng),
so raw_RMSE can move; reporting the denominator movement is required to read the deltas.

| curve | raw_now | raw_PhaseB | d_raw | lit_deg_now | lit_deg_PhaseB | d_deg |
|------|------|------|------|------|------|------|
| DTC | 14.11288 | 14.10029 | +0.09% | +10.26% | +9.99% | **+0.27 pp** |
| PEF | 1.50338 | 1.46538 | +2.59% | +14.83% | +20.09% | **-5.26 pp** |

- **DTC: denominator essentially unchanged (+0.09%), degradation stable (+0.27 pp).** The re-run
  puts DTC at 10.26% vs Phase B's 9.99% — i.e. DTC at cb15360 p32 **straddles the 10% bar** (lands
  on either side across subsamples). Confirms the advisor's read that DTC at p32 is effectively AT
  the bar, not inside it.
- **PEF: denominator moved +2.59%, but degradation moved -5.26 pp** (20.09% -> 14.83%). The small
  denominator shift cannot explain a 5 pp degradation swing, so **PEF's degradation is genuinely
  unstable to the imputer subsample (~+/-5 pp)** — reinforcing PEF as a noisy/ill-determined target.
  PEF fails the 10% bar robustly regardless (14-20% band, never near 10%).

## 5. PATCH-16 STRUCTURAL RETRY (the patching hypothesis + DTC insurance)
Within-session, same methodology (controls for subsample), cb15360:
- **PEF literal: 14.83% (p32) -> 13.84% (p16) = FLAT** (~1 pp, inside PEF's ~5 pp subsample noise).
  Per the pre-registered rule, a flat PEF response at patch 16 **CLOSES the retry question. Not the
  "19% toward 12%" strong-but-insufficient case; Pod does NOT proceed to patch 8.** PEF is confirmed
  structural / patch-insensitive, consistent with the advisor's upstream-of-the-codebook diagnosis.
- **DTC literal: 10.26% (p32) -> 9.20% (p16).** Patch 16 gives DTC modest real headroom (~0.8 pp
  inside, stability ~0.3 pp), moving it from the p32 bar-straddle to more robustly under 10% — DTC
  insurance partially delivered, though not "comfortably" inside.
- Note the cost: patch 16 doubles sequence length vs patch 32 (16 patches/512-window -> 32). G3
  budget check is the advisor's before any seal.

## 6. CROSS-BASIN LITERAL + MATCHED (Kansas <-> Netherlands; matched = imputer retrained on recon train)
raw_reference = raw imputer on raw eval; LITERAL = raw imputer on recon eval; MATCHED = recon-trained
imputer on recon eval. Both vs the same raw_reference. DTS degenerate (0 eval wells) in NLOG->KGS.

### Direction KGS->NLOG (train kgs_train / eval nlog_dev)  — headline three deg %
| config | metric | median | max | DTC | RHOB | NPHI | PEF |
|------|------|------|------|------|------|------|------|
| cb4375 p32  | LIT | +0.19 | +5.70 | -0.84 | -1.48 | +0.70 | +3.71 |
| cb4375 p32  | MAT | +0.25 | +8.01 | +0.32 | +6.29 | -0.89 | -2.19 |
| cb15360 p32 | LIT | +0.41 | +5.01 | -0.40 | +0.41 | +0.06 | +4.63 |
| cb15360 p32 | MAT | +0.96 | **+12.77** | +0.96 | **+12.77** | -1.03 | -1.78 |
| cb15360 p16 | LIT | +0.06 | +5.17 | -0.61 | -0.52 | +0.25 | +4.26 |
| cb15360 p16 | MAT | +0.38 | +9.27 | +1.48 | **+9.27** | -4.06 | +0.38 |

### Direction NLOG->KGS (train nlog_train / eval kgs_dev)  — headline three deg %
| config | metric | median | max | DTC | RHOB | NPHI | PEF |
|------|------|------|------|------|------|------|------|
| cb4375 p32  | LIT | +0.12 | +1.83 | +1.83 | +0.36 | -0.68 | -0.97 |
| cb4375 p32  | MAT | +1.45 | **+14.45** | -5.39 | +0.61 | **+14.45** | +6.32 |
| cb15360 p32 | LIT | +0.22 | +1.11 | +0.84 | +0.35 | -0.34 | -0.47 |
| cb15360 p32 | MAT | +1.97 | **+17.48** | -2.36 | +1.12 | **+17.48** | +9.24 |
| cb15360 p16 | LIT | +0.10 | +0.57 | +0.57 | +0.13 | -0.13 | -1.11 |
| cb15360 p16 | MAT | +2.52 | **+21.81** | -3.51 | +0.66 | -2.77 | +21.81 |

Cross-basin observations:
- **LITERAL passes the bar cleanly in every cell, both directions** (max 5.70% worst; PEF cross-basin
  literal is small, +3-5% or negative). PEF only fails the *pooled global-dev* literal (§3), not the
  cross-basin literal — the global-dev is the higher-powered measurement (125 PEF wells, tighter
  denominator).
- **MATCHED fails the max bar in multiple cells** (RHOB +12.77%, NPHI +14.45%/+17.48%, PEF +21.81%,
  RDEP +18% — see full tables in the JSON) and does NOT give a clean all-curve pass.

### Symmetry guard (disqualifying): matched worse than literal on a headline curve
**VIOLATED in ALL SIX direction x config cells.** Per-cell worst headline offender:
- cb4375 p32 KGS->NLOG: RHOB (lit -1.48 -> mat +6.29). NLOG->KGS: NPHI (lit -0.68 -> mat +14.45).
- cb15360 p32 KGS->NLOG: RHOB (lit +0.41 -> mat +12.77). NLOG->KGS: NPHI (lit -0.34 -> mat +17.48).
- cb15360 p16 KGS->NLOG: RHOB (lit -0.52 -> mat +9.27). NLOG->KGS: RHOB (lit +0.13 -> mat +0.66, mild).
The matched (retrained-on-tokens) imputer markedly DESTABILIZES RHOB and NPHI cross-basin. Per the
pre-registration this **disqualifies the matched metric in every cell** and shows it sinks rather
than rescues. **Branch 2 (matched-metric pass) is NOT met.**

## 7. PEF baseline + per-basin distribution (rail check)
PEF raw baseline imputation RMSE (global dev) = **1.503** this session (Phase B 1.465; §4). Per-basin
PEF over TRAIN (physical PE units; PEF is stored physical, not log10):

| basin | n | median | max | frac exactly 20.0 | frac >6 | frac in[1.5,6] | wells touching 20.0 |
|------|------|------|------|------|------|------|------|
| KGS (Kansas) | 5,135,458 | 3.460 | 20.000 | 0.017% | 1.77% | 92.74% | 3 |
| NLOG (Netherlands) | 1,356,242 | 3.958 | 20.000 | 0.001% | 17.39% | 81.96% | 9 |
| FORCE (Norway) | 649,208 | 4.238 | 20.000 | 0.000% | 22.06% | 77.18% | 3 |

Finding, from data (not assumed):
- **The hard max at 20.0 is NOT a clip/sentinel pile-up (R4 rail): mass at exactly 20.0 is
  negligible** (0.017% / 0.001% / 0.000%; only 3-9 wells touch it). So 20.0 is merely touched, not
  a rail. That distinction was the point of the check.
- **There IS a strong cross-basin PEF distribution shift**: the upper tail above the typical 1.5-6
  band grows 1.77% (Kansas) -> 17.39% (Netherlands) -> 22.06% (Norway), medians 3.46 -> 3.96 -> 4.24.
  So PEF genuinely differs across basins (heavier heavy-mineral/high-PE tails outside Kansas). This
  makes PEF's cross-basin baseline intrinsically harder and its relative-degradation bar more
  punitive, but as a **distribution shift, not a data-quality rail** — a flag for BENCHMARK.md.

## 8. Outcome-tree branch the data indicates (REPORT, not a ruling)
- **Branch 1 (clean LITERAL pass): NOT met.** PEF exceeds 10% under the literal floor at both patches
  (13.65-14.83%); patch 16 does not clear PEF. DTC reaches +9.20% at patch 16 (modest margin), but
  branch 1 fails on PEF regardless.
- **Branch 2 (matched-metric pass): NOT met.** The matched cross-basin metric violates the symmetry
  guard in all six cells (matched worse than literal on a headline curve; RHOB/NPHI up to +12-17%)
  and fails the max bar in several cells. It cannot be the operative rescue metric.
- **Between branch 3 and branch 4 (the deciding question, for the advisor):**
  - Under the literal floor alone at patch 16, **only PEF exceeds 10%** and the headline three are
    inside (DTC +9.20%, RHOB +1.39%, NPHI -0.67%) — a **branch-3 shape** (PEF-only failure; PEF
    additionally shown structural/patch-insensitive and cross-basin distribution-shifted).
  - But the **faithful matched metric sinks headline curves cross-basin** (RHOB/NPHI +9-17%) and
    fails its own symmetry guard everywhere — a **branch-4 signal** ("any headline curve fails or is
    marginal under the faithful metric").
  - The deciding question is therefore the advisor's: whether the matched metric's headline failures
    are trusted as real downstream harm (**-> branch 4, no approval, rethink patch/allocation/
    tokenizer-vs-continuous**), OR the matched metric is treated as disqualifying ITSELF via the
    symmetry guard (a one-way ratchet that misbehaved), so the literal floor governs and the residual
    failure is PEF-only (**-> branch 3, documented PEF carve-out flavor (a), still tokenized/an input/
    not gating, at the config maximizing headline margin**). Pod does not choose between these.

DTC handling (per ruling): DTC's degradation is a stated model-card limitation with its dev-well
count (319 wells), never reported as "passing" without the margin; it straddles the bar at patch 32
(9.99%/10.26%) and is +9.20% at patch 16. DTS (3 wells) non-robust, gates nothing.

## 9. Artifacts, HEAD, env, tarball
- `scripts/basinshift/fsq_diag.py` (driver), `fsq_diag_smoke.py` (plumbing smoke), `pef_rail_check.py`,
  `extract_digest.py`.
- `reports/basinshift/fsq_diag/results/{cb4375_p32,cb15360_p32,cb15360_p16}.json` (full per-curve,
  both metrics, both directions, symmetry), `fsq_diag_summary.json`, `raw_reference_global_dev.json`,
  `raw_reference_cross_basin.json`, `pef_baseline_per_basin.json`, `pef_rail_check.json`, `diag_log.txt`.
- `docs/decisions/6p3_gate_ruling_e1029b20.md` (ruling verbatim + pre-reg + appended erratum).
- `docs/fsq_6p3_diag_env_2026-07-23.txt` (pip freeze). HEAD local == remote (section 1 / §9 commit).
- 6.3 off-pod evidence tarball built with sha256 (rule 5); path + sha in the commit / handback.

## 10. HOLD
Holding for the advisor to rule the branch and the gate on this evidence. Pod has ruled nothing,
sealed nothing, carved out nothing, and does not touch open-10 or any holdout. Awaiting the advisor's
decision (branch 3 PEF carve-out flavor (a), branch 4 no-approval/rethink, or a directed next step).
