# TS-FM Stage 1 (R7, roadmap 6.2) — Phase B completion report

Paid A40 run, schedule LOCKED by Plan. 12-cell single-target, 3 systems x 12 = **36 adapter fits**.
Batch 32, **600 steps/cell** (base; not extended), LoRA q,v r=8 alpha=16, seed 20260715. Everything
scored through `scripts/basinshift/eval_harness.py` (sole scorer, physical units, population identity
asserted). blind_force never loaded. Outside the hashed set; corpus freeze d5b35a00 untouched.

## Cost (actual vs estimate)
- Wall-clock **80378.3s = 22.33 h** on one A40; **~$9.82** @ $0.44/hr.
- Estimate was ~$10 (expected) / ~$12.4 (high). Actual **$9.82** — within the $20 / 2-day ceiling.
- Micro-benchmark measured A40 0.112 s/window (speedup 38-65x vs the 96-core CPU smoke).

## Dev selection (A vs B, physical-unit RMSE via harness on in-train-basin dev wells)
- Scale-fair rel-metric: **A=0.9369** vs B=0.9502 -> **winner = pretrained-A** (channel-mean pool). Control = random-init config A.

## 12-cell results: adapted TS-FM (pretrained-A) vs XGBoost, + control delta
impr%% = TS-FM RMSE improvement over XGBoost (negative = worse). ctrl_delta = random_RMSE - pretrained_RMSE (positive = pretraining helps).

| cell | tgt | TSFM | XGB | impr% | control | ctrl_delta |
|---|---|---|---|---|---|---|
| A_cross_to_norway | DTC | 33.5732 | 15.9436 | -110.6 | 32.4065 | -1.1667 |
| A_cross_to_norway | RHOB | 0.2385 | 0.1280 | -86.4 | 0.2417 | +0.0032 |
| A_cross_to_norway | NPHI | 0.1541 | 0.0701 | -119.9 | 0.1629 | +0.0087 |
| B_cross_to_kansas | DTC | 31.4051 | 30.4535 | -3.1 | 31.5590 | +0.1540 |
| B_cross_to_kansas | RHOB | 0.2131 | 0.4791 | +55.5 | 0.2080 | -0.0051 |
| B_cross_to_kansas | NPHI | 0.1389 | 0.2539 | +45.3 | 0.1262 | -0.0128 |
| C1_in_kansas | DTC | 18.4085 | 12.6058 | -46.0 | 23.1251 | +4.7167 |
| C1_in_kansas | RHOB | 0.2088 | 0.1250 | -67.0 | 0.2448 | +0.0361 |
| C1_in_kansas | NPHI | 0.1019 | 0.0839 | -21.4 | 0.1184 | +0.0165 |
| C2_in_norway | DTC | 24.1182 | 6.6576 | -262.3 | 27.5846 | +3.4665 |
| C2_in_norway | RHOB | 0.2270 | 0.0942 | -141.0 | 0.2445 | +0.0175 |
| C2_in_norway | NPHI | 0.1161 | 0.0596 | -94.7 | 0.1204 | +0.0043 |

## Escalation-clause check (cross-basin dirs A,B; >25% on ALL of DTC/RHOB/NPHI)
- **DTC**: per-dir impr [-110.6, -3.1]; pooled TSFM=32.8554 XGB=21.9555 -> **-49.6%** (>25%: False).
- **RHOB**: per-dir impr [-86.4, 55.5]; pooled TSFM=0.2177 XGB=0.4392 -> **+50.4%** (>25%: True).
- **NPHI**: per-dir impr [-119.9, 45.3]; pooled TSFM=0.1419 XGB=0.2312 -> **+38.6%** (>25%: True).

**ESCALATION: DOES NOT FIRE.** DTC is worse than XGBoost cross-basin (pooled -49.6%), so the '>25% on all three curves' condition fails. Recorded, proceed to seal.

### Interpretation
- XGBoost remains the stronger overall baseline at 600 steps: TS-FM is worse on **DTC** everywhere and worse on all targets generalizing **to Norway** (dir A, dir C2).
- TS-FM has a real, specific strength: generalizing **cross-basin to Kansas** (dir B) it beats XGBoost by **+50.4%% (RHOB)** and **+38.6%% (NPHI)** pooled — porosity/density transfer.
- Final training losses were still descending at 600 steps, so these are a **budget-bounded floor** on TS-FM capability (steps not extended, to keep the run reproducible and well inside ceiling).

## Control delta (measured pretraining contribution)
- Mean RMSE: pretrained **9.0753** vs random **9.6785**; pretrained beats random in **9/12** cells. Largest positive deltas are in-basin DTC (C1 +4.72, C2 +3.47).
- The delta is **modest** — generic temporal pretraining transfers only weakly here. Per the R7 annex this is **evidence supporting the from-scratch S-model design** for Stage 2 (small delta).

## Frozen predictions (immutable; Stage 2 compares the S-model against these)
- `reports/basinshift/phaseB/frozen_adapted_pretrained_A.json.gz` sha256 **9b41fa56f30b9b19ff089b00549b9f4156d9975833d45145074f49feb8122d31** (39168241 bytes)
- `reports/basinshift/phaseB/frozen_control_random_A.json.gz` sha256 **47ba1cc55d1e4eef767653a7fab45e4b11a3573739cf818bff45c6a8ce54d1a3** (37398226 bytes)
- Each = gzip(deterministic, mtime=0) of {cell:{target:{metrics, test_preds, dev_preds}}} with sorted keys. Never re-tune. Raw per-fit files (incl. pretrained-B) are in the off-pod tarball.
- **Durable frozen-prediction identity = the committed `.gz` sha256s above.** The earlier raw-JSON shas (adapted `1ac9c771...09a6b1`, control `b45cd96a...29d5233`) are SUPERSEDED by the deterministic re-serialization to gzip -- predictions unchanged, only the on-disk container changed (R5 stated-cause). No re-commit of the predictions themselves.

