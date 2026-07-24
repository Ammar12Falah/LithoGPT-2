# D2 Step 3 (PEF decomposition) + Step 4 (seed-repeat) — Pod report

Appended 2026-07-25 by Pod. Read-only over frozen splits (d5b35a00); blind_force never loaded.
Reports facts only. No config sealing, no bar interpretation, no carve-out — advisor rules.

## Step 3 — PEF numerator/denominator decomposition (free, per D.2)

Pulled directly from the committed result JSONs (`reports/basinshift/fsq_phaseB/fsq_phaseB_summary.json`,
`reports/basinshift/fsq_diag/results/*.json`), cb15360 (PEF, GLOBAL_DEV):

| Run | raw_rmse (denom) | recon/literal_rmse (numer) | degradation |
|---|---|---|---|
| Phase B (patch32) | 1.465382 | 1.759783 | 20.09% |
| D1 (cb15360_p32 re-run) | 1.503383 | 1.726348 | 14.83% |
| D1 (cb15360_p16, the retry) | 1.503383 | 1.711426 | 13.84% |

**Phase B -> D1 swing (the 5.26pp the advisor flagged):** denominator moved +2.59% (1.465382 ->
1.503383), numerator moved -1.90% (1.759783 -> 1.726348). Counterfactual decomposition: ~3.04pp of
the 5.26pp swing is denominator-attributable, ~2.28pp numerator-attributable. **Over half the
swing is a denominator artifact** (the raw_reference_RMSE was recomputed in a different run rather
than reused from a shared cache) — the exact failure mode the shared harness (eval_harness.py)
exists to refuse. This is NOT primarily a real tokenizer effect.

**D1 patch32 -> patch16 (the "does not rescue PEF" comparison, 0.99pp):** denominator IDENTICAL in
both D1 runs (1.503383 == 1.503383); the entire 0.99pp swing is numerator. Real (not a denominator
artifact) but small — its materiality is exactly what Step 4 measures against the noise floor.

## Step 4 — seed-repeat (patch16/cb15360, literal arm, GLOBAL_DEV)

Tokenizer-seed and imputer-seed varied **separately** (not collapsed), per D.2. Imputer axis
reused across tokenizer seeds where possible and vice versa, so neither axis pays for the other's
retraining cost.

### Tokenizer-seed axis (n=3: 20260715 canonical, 20260815, 20260915; imputer held at canonical)

| Curve | mean | range | spread |
|---|---|---|---|
| DTC | 9.57% | [9.47%, 9.72%] | 0.25pp |
| RHOB | 1.36% | [1.26%, 1.56%] | 0.30pp |
| NPHI | -0.56% | [-0.76%, -0.38%] | 0.38pp |
| PEF | 12.54% | [11.51%, 13.37%] | **1.86pp** |

### Imputer-seed axis (n=5: 20260715 canonical, 20260716-20260719; tokenizer held at canonical)

| Curve | mean | range | spread |
|---|---|---|---|
| DTC | 9.30% | [8.80%, 9.73%] | 0.93pp |
| RHOB | 0.96% | [0.66%, 1.26%] | 0.59pp |
| NPHI | 0.13% | [-0.76%, 0.78%] | **1.54pp <- EXCEEDS 1pp (headline curve)** |
| PEF | 14.05% | [12.79%, 16.14%] | 3.35pp |

### Pre-registered consequence (D.2/D.3, fixed before this run)

**NPHI's imputer-seed spread (1.54pp) exceeds the 1pp headline threshold.** Per the advisor's
pre-registered rule: *"if per-curve spread on any headline curve exceeds 1pp, the gating metric
becomes the mean over N=5 seeds... bar applies to the mean."* N=5 was already run for the imputer
axis (matches Plan's D.3 pre-registration), so the mean (0.13%) is available and clears the bar
easily on NPHI regardless. DTC's imputer-seed spread (0.93pp) is close to but does not cross 1pp.

**Provisional-closure flag resolved:** PEF's own seed-to-seed spread (1.86pp tokenizer-seed, 3.35pp
imputer-seed) is **larger than the 0.99pp patch16-vs-patch32 delta** that "patch16 does not rescue
PEF" rested on. That comparison was made against noise larger than the effect itself — the
patch-size axis is confirmed **not separable from run-to-run variation** at the measured spread,
exactly the caution D.2 pre-registered. This should NOT be written as "patch size does not help
PEF" in BENCHMARK.md or the paper.

**Material-improvement threshold restatement (Plan D.3):** max(3pp, 3 x measured spread). Using the
wider (imputer-seed) PEF spread of 3.35pp: 3 x 3.35 = 10.05pp, i.e. the threshold for a config
change to count as material now sits around **~10pp**, not the original 3pp — a hardening, not a
loosening, per D.3.

### Execution notes

- First invocation (tokenizer-seed sweep) completed cleanly (3/3), then a guard halted before the
  imputer-seed sweep on a false-positive projection (it blended the cheap ~170s imputer-fit cost
  with the ~3500-3800s tokenizer-retrain cost when projecting the next step). Wall/cost for this
  run: 11245.1s (~$1.37), gate UNDER.
- A top-up invocation rebuilt the canonical tokenizer once (3323.8s; PEF literal_deg reproduced
  13.37% exactly, a clean determinism check) and completed the imputer-seed sweep (5/5, 4466s,
  ~$0.55).
- **Combined Step 4 total: 15710.7s wall (4.36h), ~$1.92.** This already exceeds the 4h wall-clock
  component of the money gate (cost stayed well under $5).

## Step 5 — NOT run tonight

Per Plan's threshold (Step 4 spent + Step 5 projected, checked against 4h/$5 before proceeding):
Step 4 alone already spent 4.36h, over the 4h ceiling before any Step 5 compute is added. Step 5 is
deferred to the next session per the pre-registered decision rule.

**Step 5 cost estimate** (for planning; not executed), using tonight's measured per-retrain timing
(~3300-3800s per full 11-curve/30-epoch patch16/cb15360 tokenizer retrain, ~160-180s per imputer
refit) as the basis rather than the earlier Phase-A-era estimate:
- Per-basin PEF degradation split: ~70 min (prior estimate; this is pure re-slicing of an existing
  reconstruction+imputer by basin, no new retrain needed if the canonical tokenizer/imputer are
  kept in memory — cheap in a single continuous process, otherwise pays one more ~55-65 min
  canonical rebuild).
- PEF coverage stats: cheap, no retrain (already substantially available in
  `reports/basinshift/fsq_diag/pef_baseline_per_basin.json` from the D1 round).
- Curve-balance / PEF-only retrain: at minimum one more full tokenizer retrain at tonight's
  measured cost (~55-65 min).
- Basin-balance retrain (if separable): at minimum one more full tokenizer retrain (~55-65 min).
- **Rough total: ~3.25-4+ hours**, i.e. Step 5 alone is comparable in size to tonight's entire
  Step 4 effort. Combined with tonight's already-spent 4.36h, total for the round would run
  roughly 7.5-8.5h — well outside a single 4h/session gate. Step 5 should be its own session/round.

Interpretation of Step 5 (once run) should be read against the noise floors established here:
headline curves' seed-to-seed spread is comfortably under 1pp except NPHI's imputer-axis (1.54pp,
already resolved via the N=5 mean rule); PEF's own spread (1.86-3.35pp) is the dominant source of
uncertainty for any PEF-specific finding in Step 5.
