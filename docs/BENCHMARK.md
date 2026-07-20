# BENCHMARK

## 2026-07-11 Architecture decision capture (advisor ruling, reviewed not absorbed silently)

Verbatim ruling:
"Method for the transfer track is a from-scratch decoder-only transformer. A LoRA-adapted open time-series foundation model runs as a two-day baseline immediately after benchmark freeze, evaluated on dev and open-leaderboard wells only. Pre-registered tripwire: if the adapted TS-FM beats the from-scratch S-model cross-basin on the dev slice by more than 10 percent relative RMSE on at least two of three target curves, a scope amendment is brought before further training spend. The FORCE blind wells are touched once, by the final scoring path, and never by selection, comparison, or tripwire evaluation."

Recorded per advisor amendment 4; pre-registration predates the post-benchmark-freeze TS-FM tripwire baseline. Attribution: advisor. Reviewed at capture.


---

## BasinShift — Cross-Basin Well-Log Imputation Benchmark (roadmap 6.1)

Built against the frozen corpus (manifest `d5b35a00`, split-gen `d4113797`, seed `20260715`).
Every number traces to a committed artifact or to `reports/basinshift/run_log.txt`. **This is
the design/CP1 version; the immutable BasinShift test-manifest hash is added only after Plan
clears CHECKPOINT 1 (Phase 2).**

### 1. Task
**Curve imputation under basin shift.** One canonical *target* curve is hidden per well and
predicted per depth-sample from the remaining canonical log curves plus depth.
- Targets (hidden, one per config): **DTC, RHOB, NPHI**.
- Inputs: `{GR, RHOB, NPHI, DTC, PEF, SP, CALI, RDEP, RMED, RSHA, DTS} \ {target}` + `depth_m`.
  `BS` (bit size) is excluded (borehole attribute, not a petrophysical log). Resistivities are
  used as stored (log10 ohm·m). A curve value is used only where its `_mask` is True; else NaN
  (the tree model consumes NaN natively).
- Ground truth for a well/target = the target's masked-valid samples in that well.

### 2. What is scored: cross-basin generalization (the differentiator)
The scored axis is **cross-basin transfer**, not in-distribution imputation. The contrast is
in-basin vs cross-basin RMSE **per curve**:
- **Direction A — cross → Norway.** Train `kgs.train` + `nlog.train`, test **FORCE open-10**.
- **Direction B — cross → Kansas.** Train `nlog.train` + `force2020.train`, test `test_kgs` (263).
- **Direction C — in-basin comparators.** C1 `kgs.train → test_kgs`; C2 `force2020.train →
  open-10`. Scored quantity = the **gap** A vs C2 (Norway) and B vs C1 (Kansas), per curve.

Dev (`kgs.dev` 339, `nlog.dev` 257) is reserved for tuning; **no holdout is ever used for
tuning**. `nlog.test_nlog` (341) is reserved (no NLOG-target direction in this build).
**FORCE blind-10 is never touched** (§7).

**Differentiation (state explicitly, do not conflate):**
- **Gama et al. 2025** (*Computers & Geosciences* 196, 105789) benchmark imputation
  **in-distribution**. BasinShift scores **held-out-basin generalization**, with in-basin
  performance only as the comparator; the baseline shows cross-basin error is 1.2–3.8× in-basin
  and, for Kansas RHOB/NPHI, worse than a constant-mean predictor — the two are not
  interchangeable.
- **WellLogBench** (OpenReview 2026) is **adjacent but a different task**; cited for context,
  its name is not reused for any BasinShift config.

### 3. Metrics
Per-curve **RMSE** and **MAE**, **pooled** over valid test target samples (primary) and
**macro-averaged over wells** (secondary). Native units (DTC µs/ft, RHOB g/cc, NPHI v/v).
**CRPS is reserved** for the later probabilistic phase; not scored now.

### 4. XGBoost baseline (standing opponent)
`scripts/basinshift/basinshift_baseline.py` (seed `20260715`). XGBRegressor `n_estimators=400,
max_depth=6, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, tree_method="hist"`.
Training samples capped at 1,000,000 per fit (seeded subsample); a test well is scored for a
target only if it has ≥100 valid target samples (`MIN_TARGET_SAMPLES`). No normalization
(trees are scale-invariant).

Results (pooled RMSE / MAE; global-mean-of-train floor in parens; `w` = scored test wells):

| Target | A cross→Norway | C2 in Norway | B cross→Kansas | C1 in Kansas |
|---|---|---|---|---|
| DTC  | 15.94 / 12.28 (floor 32.3) · 10w | **6.66** / 4.85 · 10w | 30.45 / 21.76 (floor 32.0) · **9w** | **12.61** / 6.84 · 9w |
| RHOB | 0.128 / 0.095 (floor 0.24) · 10w | **0.094** / 0.065 · 10w | 0.479 / 0.438 (floor **0.21**) · 239w | **0.125** / 0.080 · 239w |
| NPHI | 0.070 / 0.053 (floor 0.16) · 10w | **0.060** / 0.045 · 10w | 0.254 / 0.218 (floor **0.13**) · 181w | **0.084** / 0.055 · 181w |

Cross-basin RMSE exceeds in-basin on every curve; for Kansas RHOB and NPHI the cross-basin
model is **worse than predicting the training mean** — the basin-shift failure the benchmark is
built to surface.

**Data quirk (CP1 decision):** only **9 of 263** `test_kgs` wells carry ≥100 valid DTC (sonic)
samples — Kansas rarely logs sonic — so the Kansas-DTC cell (B/C1) is thin. RHOB (239) and NPHI
(181) are well-populated; Norway open-10 carries all three targets in all 10 wells. Plan to
rule: keep DTC→Kansas flagged-as-thin, or drop DTC from the Kansas direction.

### 5. Evaluation-set composition (frozen splits only)
Backing: `reports/basinshift/eval_composition.json`, `run_log.txt`.

| Run | Train pools (wells) | Test pool (wells) |
|---|---|---|
| A_cross_to_norway | kgs.train 5734 + nlog.train 1757 = 7491 | open10 10 |
| B_cross_to_kansas | nlog.train 1757 + force.train 98 = 1855 | test_kgs 263 |
| C1_in_kansas | kgs.train 5734 | test_kgs 263 |
| C2_in_norway | force.train 98 | open10 10 |

### 6. Leakage assertions (baseline run; full suite at CHECKPOINT 2)
Per run the script asserts, and `run_log.txt` records: **blind_overlap = 0** (no `blind_force`
well by well_id or safe_name), **train_test_overlap = 0**. All four runs PASS.

### 7. Standing rules
- **Blind-10 (`split == "blind_force"`, 10 wells) is never loaded**; only its names are read for
  the absence assertion. Its parquets are not present in `data/processed/force2020` (108 = 98 +
  10 open). Blind-10 is touched once, by the final scoring path at G3 (roadmap 6.6). The baseline
  script raises rather than open a blind path.
- Built against `d5b35a00` only: no re-cut splits, no reopened ingestion, no synthetic data.
- Evidence artifact, outside the hashed set; does not move `qc_code_sha256` or `d5b35a00`.

### 8. Artifacts
`scripts/basinshift/basinshift_baseline.py`; `reports/basinshift/{run_log.txt,
baseline_results.json, eval_composition.json, test_manifest_PROPOSED.json}`. The proposed
manifest is **NOT hashed** (CP1 review); the immutable hash lands after Plan clears CP1.
