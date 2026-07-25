# D2 Phase 1 — RNG defect fix, frozen baseline, Phase B re-score (Pod, 2026-07-25)

Corrective work on a confirmed defect (does not wait on any ruling), per the ATCE critical-path
brief. Reports findings; does not seal, select, or carve out anything.

## 1. The defect, its effect, and what it does NOT affect

`eval_harness.py`'s `build_train()` used a MODULE-LEVEL `rng = np.random.default_rng(SEED)`,
shared and stateful across every call within one process. `fsq_diag.py`'s `build_train_pool()`
instead created a fresh `np.random.default_rng(seed)` on every call. Same nominal seed value,
different consumption pattern: Phase B's imputer (fit once, sequentially over 11 curves via
`eval_harness.EH.build_train`) advanced the shared rng progressively across curves; D1's fresh
rng always restarted at the same point. With `TRAIN_CAP=1,000,000` and several curves' pooled
training rows exceeding that cap, this selected different subsamples under the "same" seed. This
fully explains the PEF raw_rmse drift already decomposed in the prior Step 3 report
(1.465382 -> 1.503383, ~half the Phase B->D1 swing) — confirmed now with no ambiguity, since the
frozen baseline computed under the fix (below) reproduces D1's fresh-rng numbers exactly to full
precision (e.g. PEF 1.503383, DTC 14.112876282339403).

**Read of `scripts/basinshift/fsq_phaseB_sweep.py` (code, not a run):** `build_imputers_and_raw()`
is called ONCE in `main()`, before the config loop. Phase B's 11 imputers/raw_rmse values were fit
exactly once and reused identically across all 6 sweep configs. **Phase B's own internal six-config
comparison is therefore self-consistent** — every config was scored against the same denominator.
The defect only breaks *cross-session* comparison (Phase B's denominator vs D1's, or vs anything
computed fresh today), not Phase B's internal ranking of its own 6 configs.

**Larger finding, surfaced rather than resolved unilaterally:** `scripts/basinshift/
basinshift_baseline.py` -- the script that generated the ORIGINAL committed `baseline_results.json`
-- has the **identical** module-level shared-rng pattern (`rng = np.random.default_rng(SEED)` at
its own line 30, independently written, not imported from `eval_harness.py`). This means
`baseline_results.json` itself is a snapshot whose exact values are entangled with that script's
own internal call order (4 RUNS x 3 TARGETS = 12 sequential `build_train` calls in a fixed
sequence). `eval_harness.py`'s pre-fix validation block reproduced it only because both scripts
happened to iterate the same 12 cells in the same order in every execution -- the shared state's
effect canceled out between them, not because either script's rng handling was sound. Fixing
`eval_harness.py` to use a fresh, order-independent rng per call removes that coincidental
alignment along with the defect: **post-fix, `eval_harness.py`'s validation against the ORIGINAL
`baseline_results.json` now passes only 2 of 12 cells** (`harness_validation.txt`, this session);
the other 10 differ by amounts ranging from noise-level (RHOB/NPHI, ~0.2-2.4%) to substantial
(DTC cells, up to +6.4% relative). This is not a new bug introduced by the fix -- it reveals that
`baseline_results.json` was always order-dependent and not independently re-derivable by clean
code; the fix simply stops masking that. **What `baseline_results.json` should mean going forward,
and whether `basinshift_baseline.py` needs the same fix, is not decided here** -- it touches the
reference baseline the entire 6.x roadmap has scored against and is surfaced for Plan/advisor
judgment, not resolved unilaterally.

## 2. Re-proof after the fix

`eval_harness.py` validation against `baseline_results.json`, pinned env (numpy 1.26.3, pandas
2.2.3, pyarrow 25.0.0, xgboost 3.2.0, sklearn 1.9.0): **2/12 PASS, 10/12 FAIL** (see above; full
detail in `reports/basinshift/harness_validation.txt`, this session's run). Expected and explained,
not a regression in the fix itself.

## 3. Determinism assertion added

`eval_harness.assert_build_train_deterministic(train_pools, target, seed)`: calls `build_train`
twice with identical arguments, refuses (raises `AssertionError`) unless the two results are
byte-identical. First implementation had its own bug (`np.array_equal` without `equal_nan=True`
treats `NaN != NaN`, and feature columns legitimately contain NaN for missing logs -- this fired a
false-positive "violation" on the very first curve, GR, before being caught and fixed). Corrected
version passed cleanly on all 11 canonical curves during the freeze run below.

## 4. Frozen scoring baseline

`reports/basinshift/frozen_raw_baseline_2026-07-25.json`, sha256
`d3ecb97c05472f64f0b810f7d323473abd7ee2b470a222469eedb70a9c21fae4`. GLOBAL_DEV (kgs_dev+nlog_dev),
all 11 canonical curves, imputer trained on kgs_train+nlog_train+force_train, `eval_harness.XGB`
params, `imputer_seed=20260715` frozen together with the denominator per D4. Determinism-asserted
per curve before acceptance. 451s wall, CPU only.

| Curve | raw_rmse (frozen) | n_samples | n_wells |
|---|---|---|---|
| GR | 25.684157 | 5,487,809 | 559 |
| RHOB | 0.197006 | 2,994,770 | 483 |
| NPHI | 0.073964 | 1,189,400 | 273 |
| DTC | 14.112876 | 3,266,374 | 319 |
| PEF | 1.503383 | 510,985 | 125 |
| SP | 65.297022 | 2,773,570 | 401 |
| CALI | 2.235776 | 2,659,658 | 453 |
| RDEP | 2086.344203 | 2,832,967 | 422 |
| RMED | 991.825989 | 2,329,153 | 350 |
| RSHA | 1562.950332 | 640,414 | 112 |
| DTS | 23.742481 | 27,164 | 3 |

## 5. Phase B six-config table, re-scored (arithmetic only, no retraining)

Original `recon_rmse` numerators (committed, unchanged) against the new frozen denominators.
Original figures preserved alongside for comparison, not overwritten.

| config | codebook | old median% | new median% | old max% | new max% | max curve (new) |
|---|---|---|---|---|---|---|
| cb64 | 64 | 8.78 | 7.80 | 19.46 | 16.88 | DTS |
| cb125 | 125 | 7.31 | 6.34 | 19.02 | 16.01 | PEF |
| cb240 | 240 | 4.67 | 4.90 | 19.76 | 16.73 | PEF |
| cb1000 | 1000 | 3.81 | 3.28 | 20.49 | 17.44 | PEF |
| cb4375 | 4375 | 3.46 | 2.89 | 20.42 | 17.38 | PEF |
| cb15360 | 15360 | 2.60 | 2.73 | 20.09 | 17.05 | PEF |

PEF detail (old raw_rmse 1.465382 -> new 1.503383 at every config, since Phase B used one fixed
denominator throughout):

| config | recon_rmse | old PEF% | new PEF% |
|---|---|---|---|
| cb64 | 1.750604 | 19.46 | 16.44 |
| cb125 | 1.744052 | 19.02 | 16.01 |
| cb240 | 1.754937 | 19.76 | 16.73 |
| cb1000 | 1.765572 | 20.49 | 17.44 |
| cb4375 | 1.764651 | 20.42 | 17.38 |
| cb15360 | 1.759783 | 20.09 | 17.05 |

DTC detail (headline curve):

| config | recon_rmse | old DTC% | new DTC% |
|---|---|---|---|
| cb64 | 15.913372 | 12.86 | 12.76 |
| cb125 | 15.796233 | 12.03 | 11.93 |
| cb240 | 15.821680 | 12.21 | 12.11 |
| cb1000 | 15.608753 | 10.70 | 10.60 |
| cb4375 | 15.494682 | 9.89 | 9.79 |
| cb15360 | 15.509299 | 9.99 | 9.89 |

**No gate conclusion changes.** PEF still fails the >10% single-curve bar at every one of the 6
configs (best case 16.01% at cb125, nowhere near 10%). DTC's best Phase-B value (9.79% at cb4375)
still fails the amended 8% headline bar from D.1. The relative ranking across configs (cb15360
lowest median, PEF as the binding max-curve failure in every config) is unchanged. The 1-3.5pp
uniform shift is exactly what the corrected denominator predicts and does not alter any ruling
already made against the old numbers.

## Boundaries

Nothing sealed, selected, or carved out. `baseline_results.json`'s status and whether
`basinshift_baseline.py` needs the same fix are surfaced for Plan/advisor judgment (Section 1),
not decided here. HOLD after Phase 1 per the brief; Phase 2 does not start without a report first.
