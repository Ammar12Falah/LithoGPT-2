# FSQ Tokenizer (roadmap 6.3 / R8) — Phase A Report

Status: Phase A COMPLETE. CPU only, spent nothing (no paid GPU launched, no sweep run).
Ends at the mandatory STOP: harness + acceptance path built and smoked; pre-registration and
full-sweep cost estimate proposed below for Plan to LOCK before Phase B.

Frozen splits (d5b35a00) untouched. Holdouts (test_kgs, test_nlog, open-10) RESERVED, not used.
blind_force NEVER loaded. Outside the hashed set; d5b35a00 untouched.

## 0. Preflight (all PASS)
- HEAD = `0bdd99260b5953597651fd468040953916ada35b`, local == remote (GitHub API commit endpoint
  confirmed the same SHA). Matches the expected `0bdd9926`.
- Anti-blank-sibling: kgs processed parquets = 9307; `reports/nlog_qc_records.csv` = 5005 lines.
- Depth grid uniform 0.1524 m (verified on a kgs dev parquet: min=median=max diff = 0.1524).
- Splits (`data/splits/split_assignment.csv`): kgs dev 339, nlog dev 257 (force2020 has NO dev).

## 1. Env (clean 6.3 pipeline env; NOT the momentfm env)
`pip freeze` snapshot committed to `docs/fsq_6p3_env_2026-07-22.txt`. Key pins:
numpy==1.26.3, pandas==2.2.3, pyarrow==25.0.0, scikit-learn==1.9.0, scipy==1.16.3,
xgboost==3.2.0, torch==2.4.1+cu124. (numpy bumped 1.25.2 -> 1.26.3 per the 6.3 spec.)

### Scorer proven FIRST (required before trusting any degradation number)
Ran the committed `scripts/basinshift/eval_harness.py` self-validation under this env:
**12/12 cells PASS, "HARNESS VALIDATION: ALL PASS (reproduces committed XGBoost)"**, all pooled
RMSE/MAE/macro diffs vs the committed `baseline_results.json` < ~2.3e-6, truth-as-pred = 0.
Captured verbatim to `reports/basinshift/harness_validation_6p3.txt`. The R8 metric is an
XGBoost-RMSE comparison, so this proves the scorer/adapter is byte-faithful under the 6.3 env.

## 2. Harness built (committed)
- `scripts/basinshift/fsq_tokenizer.py` — per-curve, per-patch FSQ autoencoder. Depth patch of
  32 samples on the 0.1524 m grid; encoder MLP (32->64->d) -> FSQ quantizer (levels; codebook =
  prod(levels); tanh-bound + straight-through round; no learned codebook, no commitment loss) ->
  continuous decoder MLP (d->64->32). One tokenizer per canonical curve. TRAIN-global per-curve
  z-score in the baseline's stored space (resistivity log10, else physical); de-standardized on
  decode. Patches cut on the depth grid; masked samples set to standardized mean for encode and
  the original NaN mask re-imposed on decode, so reconstruction has byte-identical missing-value
  structure to the raw curve.
- `scripts/basinshift/r8_acceptance.py` — the R8 path. Trains tokenizers on frozen TRAIN only;
  reconstructs the DEV split (kgs_dev + nlog_dev = 596 wells; force has no dev; holdouts reserved);
  for each canonical curve as an XGBoost imputation target, scores DEV predictions through the
  committed `eval_harness.score` twice — raw features vs reconstructed features (target truth stays
  raw physical) — and reports per-curve degradation = (recon_RMSE - raw_RMSE)/raw_RMSE, plus the
  median/max vs the R8 bar. REPORTS the bar comparison; does NOT self-certify (advisor gate).
- `scripts/basinshift/fsq_smoke.py`, `scripts/basinshift/count_probe.py` — CPU smoke + sizing.

Design guarantees carried from BasinShift: the raw dev predictions come from the identical
committed XGBoost adapter (same params, feats_for, inverse_transform, pools), so raw_RMSE is the
committed baseline's behavior applied to the dev split; population identity is asserted by the
shared scorer; scoring is in physical units.

## 3. CPU smoke (one config, plumbing only) — `reports/basinshift/fsq_smoke.json`
Config: levels (8,6,5) codebook 240, patch 32, epochs 3, cap 30k patches/curve. Tokenized all 11
canonical curves; reconstructed 596 dev wells x 11 curves; scored 2 targets end-to-end:
- DTC : raw_RMSE=14.1129 -> recon_RMSE=21.8088, degradation +54.53%  (n=3,266,374, wells=319)
- NPHI: raw_RMSE= 0.0743 -> recon_RMSE= 0.1142, degradation +53.63%  (n=1,189,400, wells=273)
- median_deg=0.5408, max_deg=0.5453 (bar: median<=0.05, max<=0.10 -> would FAIL, as expected).
Wall 366 s. The path runs; degradation is large purely because the config is deliberately tiny
(3 epochs, 30k patches, codebook 240). Population/shape assumptions held (scorer asserted identity;
NaN mask preserved through reconstruction). Plumbing goal met, not a quality result.

## 4. Proposed PRE-REGISTRATION (for Plan to LOCK before Phase B)

(a) **Patch size = 32 samples.** 32 x 0.1524 m = 4.877 m depth window — bed/parasequence scale
    typical for log interpretation; a power of two that divides the 512-sample Stage-1 window into
    exactly 16 patches (clean interop with the S-model context); small encoder input for a fast,
    low-parameter tokenizer while spanning enough depth for FSQ to capture curve shape.
    Non-overlapping on the depth grid, zero-padded tail.

(b) **FSQ level-config sweep grid (4 configs).** Codebook = prod(levels); level vectors per
    Mentzer et al. 2023 (FSQ) recommended tables for uniform code usage at each size:
      - codebook   256  : levels [8, 6, 5]        (=240)
      - codebook  1024  : levels [8, 5, 5, 5]     (=1000)
      - codebook  4096  : levels [7, 5, 5, 5, 5]  (=4375)
      - codebook 16384  : levels [8, 8, 8, 6, 5]  (=15360)
    Fixed across the grid: patch=32, hidden=64, epochs, lr, seed=20260715, standardization.

(c) **Selection rule (pre-declared).** Among configs that MEET the R8 bar (median degradation
    across canonical curves <= 5% AND no single canonical curve > 10%), select the SMALLEST
    codebook (favor a compact vocabulary for the downstream S-model). Tie-break 1: lowest median
    degradation; tie-break 2: lowest max single-curve degradation; tie-break 3: fewer FSQ dims.
    If NO config meets the bar, none is selected and the result escalates to advisor — the bar is
    NOT relaxed.

(d) **Per-curve standardization.** TRAIN-global per-curve z-score: mean/std over all finite TRAIN
    samples of that curve in the committed baseline's stored space (RDEP/RMED/RSHA in log10;
    GR/RHOB/NPHI/DTC/PEF/SP/CALI/DTS physical); std floored at 1e-6. Applied before FSQ, inverted
    on decode so reconstructions feed XGBoost in exactly the raw curve's space.

### OPEN QUESTIONS for Plan to resolve at the lock (genuine design choices that move R8 pass/fail)
1. **Which curves count in "median across canonical curves".** Built as all 11 canonical curves,
   each as an XGBoost imputation target (features = other 10 + depth), degradation from
   reconstructing the feature curves. The committed baseline only pre-defines DTC/RHOB/NPHI as
   targets; the other 8 imputers are NEW but use the identical committed machinery/params/pools.
   Recommendation: all 11 (the R8 bar says "canonical curves," and the tokenizer must reconstruct
   every curve it emits). Alternative: restrict to the 3 committed targets. Plan must LOCK the set.
2. **Dev imputer train pool.** Using all three TRAIN pools (kgs+nlog+force), global, since dev
   spans kgs+nlog. Confirm or restrict.

## 5. Full-sweep cost/time estimate
Measured (CPU, this pod): TOTAL train patches = 8,477,105 across 11 curves; FSQ training
throughput = 162,710 patch-steps/sec (torch, batch 4096; probed on a 200k real bank, 3 epochs,
3.7 s). Per-curve bank sizes in `reports/basinshift/fsq_sweep_sizing.json`.

Assume E=30 epochs/config (smoke loss still descending at 3; conservative full budget):
- Training per config = 8.477M x 30 / 162,710 ≈ 1,563 s ≈ 26.0 min.
- ONE-TIME, shared across all configs: load train cache ≈ 200 s; train the 11 XGBoost imputers on
  raw TRAIN and compute raw_RMSE ≈ 500 s (≈ 8 min). The imputers are tokenizer-independent, so
  raw_RMSE is fixed and computed once (the denominator for every config).
- Acceptance per config = reconstruct 596 dev wells x 11 curves + 11 dev inference passes ≈ 90 s.
- **4-config grid: 4 x (26.0 + 1.5) min + 8 + 3 ≈ 121 min ≈ 2.0 h CPU.**
- 6-config grid (if expanded): ≈ 2.9 h CPU. E=50 raises the 4-grid to ≈ 3.1 h (still < 4 h).

Dollar: on the already-running A40 pod, CPU time bills at the A40 rate $0.44/hr (sourced:
Stage-1 Phase B was $9.82 for 22.3 h on one A40 = $0.440/hr). 2.0 h -> ~$0.90; 2.9 h -> ~$1.28.

GPU (A40) would cut FSQ training ~10x (tiny MLP, batch 4096) but XGBoost stays CPU; total
~30-40 min, ~$0.25. **Not required.**

**Verdict: the full sweep is UNDER the money gate (<= $5 AND <= 4 h) on CPU for a 4-6 config grid
at 30 epochs. No paid-GPU escalation needed; recommend running the sweep on CPU on the existing pod.**

## 6. STOP / HOLD
Holding for Plan to LOCK the pre-registration (patch size, grid, selection rule, standardization,
and the two open questions). No sweep, no paid GPU, no R8 self-certification until then. When
locked, the Phase B driver trains the imputers once, then sweeps the locked grid on CPU.
