#!/usr/bin/env python3
"""R8 acceptance path for the FSQ tokenizer (roadmap 6.3).

Pipeline, all routed through the committed BasinShift machinery (eval_harness):
  1. Train one FSQ tokenizer per canonical curve on the frozen TRAIN split ONLY.
  2. Tokenize-then-reconstruct every DEV well's curves (dev = kgs_dev + nlog_dev; force has no
     dev split; test_* and open-10 are RESERVED and NOT touched; blind_force NEVER loaded).
  3. For each canonical curve C used as an imputation target, train the committed XGBoost
     imputer (eval_harness.build_train + committed XGB params) on RAW TRAIN, then score its
     DEV predictions in physical units twice through eval_harness.score:
        raw_RMSE   = XGB on RAW dev features
        recon_RMSE = XGB on RECONSTRUCTED dev features (target-curve truth stays raw physical)
     per-curve degradation = (recon_RMSE - raw_RMSE) / raw_RMSE.

R8 bar (fixed by R8, NOT alterable here): median degradation across canonical curves <= 5%
AND no single canonical curve > 10%. This script REPORTS the numbers and the bar comparison;
it does NOT self-certify. Pass/fail is an advisor gate at Phase B end.

The raw dev XGBoost predictions are produced by the identical committed adapter, so raw_RMSE is
the committed baseline's behavior applied to the dev split (the 12-cell reproduction that proves
this adapter is byte-faithful under the 6.3 env is eval_harness.py's own __main__).
"""
import json, time
from pathlib import Path
import numpy as np
from xgboost import XGBRegressor

import eval_harness as EH
import fsq_tokenizer as FT

OUT = EH.ROOT / "reports/basinshift"
TRAIN_POOLS = ["kgs_train", "nlog_train", "force_train"]   # global tokenizer + global imputer
DEV_SPECS = [("kgs", "dev"), ("nlog", "dev")]


def dev_wells():
    w = []
    for src, split in DEV_SPECS:
        w += EH.wells_of(src, split)
    return w


def curve_arrays_train(curve):
    """All stored-space arrays of `curve` across TRAIN pools (list of 1-D np arrays)."""
    arrs = []
    for pool in TRAIN_POOLS:
        for (src, safe, wid) in EH.POOLS[pool]:
            df = EH.load_well(src, safe, wid)
            arrs.append(df[curve].to_numpy())
    return arrs


def train_all_tokenizers(curves, levels, epochs, cap, log):
    """Return {curve: (model, mean, std)} trained on TRAIN only."""
    toks = {}
    for c in curves:
        t0 = time.time()
        arrs = curve_arrays_train(c)
        mean, std = FT.compute_stats(arrs)
        bank = FT.build_patch_bank(arrs, mean, std, cap=cap)
        log(f"  [tok {c}] patches={len(bank)} mean={mean:.4g} std={std:.4g}")
        model = FT.train_tokenizer(bank, levels, epochs=epochs, log=log)
        toks[c] = (model, mean, std)
        log(f"  [tok {c}] trained in {time.time()-t0:.1f}s")
    return toks


def reconstruct_dev(toks, log):
    """{ (src,safe): {curve: recon_stored_array} } for all dev wells and all tokenized curves."""
    recon = {}
    wells = dev_wells()
    for i, (src, safe, wid) in enumerate(wells):
        df = EH.load_well(src, safe, wid)
        rc = {}
        for c, (model, mean, std) in toks.items():
            rc[c] = FT.reconstruct_curve(df[c].to_numpy(), model, mean, std)
        recon[(src, safe)] = rc
    log(f"  reconstructed {len(wells)} dev wells x {len(toks)} curves")
    return recon


def dev_grid(target):
    grid = []
    for (src, safe, wid) in dev_wells():
        df = EH.load_well(src, safe, wid)
        y = df[target].to_numpy()
        valid = np.where(~np.isnan(y))[0]
        if len(valid) < EH.MIN_TARGET_SAMPLES:
            continue
        grid.append((wid, valid, EH.inverse_transform(target, y[valid])))
    return grid


def _wid_lookup():
    return {wid: (src, safe) for (src, safe, wid) in dev_wells()}


def predict_dev(target, model_xgb, recon=None, lut=None):
    """Predict `target` on dev. recon=None -> raw features; else replace feature curves with
    their reconstruction. Returns (grid, preds_by_well) in physical units."""
    feats = EH.feats_for(target)
    grid = dev_grid(target)
    lut = lut or _wid_lookup()
    preds = {}
    for (wid, valid, _y) in grid:
        src, safe = lut[wid]
        df = EH.load_well(src, safe, wid)
        if recon is None:
            X = df[feats].to_numpy()[valid]
        else:
            rc = recon[(src, safe)]
            cols = []
            for f in feats:
                col = df[f].to_numpy() if f == "depth_m" else rc[f]
                cols.append(np.asarray(col)[valid])
            X = np.column_stack(cols)
        preds[wid] = EH.inverse_transform(target, model_xgb.predict(X))
    return grid, preds


def run(levels, curves=None, score_curves=None, epochs=8, cap=None, log=print):
    """Full R8 path. Returns a results dict; also usable for the CPU smoke with small settings.

    `curves`       : curves to TOKENIZE (must cover every feature curve of each scored target).
    `score_curves` : curves to score degradation for (default = `curves`). Lets the smoke
                     tokenize all feature curves but score a cheap subset of imputers.
    """
    curves = curves or EH.CANON
    score_curves = score_curves or curves
    t0 = time.time()
    log(f"=== R8 acceptance: FSQ levels={list(levels)} codebook={int(np.prod(levels))} "
        f"tokenize={len(curves)} score={len(score_curves)} epochs={epochs} cap={cap} ===")
    toks = train_all_tokenizers(curves, levels, epochs, cap, log)
    recon = reconstruct_dev(toks, log)
    lut = _wid_lookup()

    per_curve = {}
    for tgt in score_curves:
        feats = EH.feats_for(tgt)
        # reconstructed condition requires every FEATURE curve to be tokenized
        if any(f != "depth_m" and f not in toks for f in feats):
            log(f"  [deg {tgt}] SKIP (a feature curve was not tokenized in this run)")
            continue
        Xtr, ytr = EH.build_train(TRAIN_POOLS, tgt)
        m = XGBRegressor(**EH.XGB)
        m.fit(Xtr, ytr)
        g_raw, p_raw = predict_dev(tgt, m, recon=None, lut=lut)
        g_rec, p_rec = predict_dev(tgt, m, recon=recon, lut=lut)
        raw = EH.score(g_raw, p_raw, tgt)
        rec = EH.score(g_rec, p_rec, tgt)
        deg = (rec["pooled_rmse"] - raw["pooled_rmse"]) / raw["pooled_rmse"]
        per_curve[tgt] = dict(raw_rmse=raw["pooled_rmse"], recon_rmse=rec["pooled_rmse"],
                              degradation=deg, n_samples=raw["n_samples"], n_wells=raw["n_wells"])
        log(f"  [deg {tgt}] raw_RMSE={raw['pooled_rmse']:.4f} recon_RMSE={rec['pooled_rmse']:.4f} "
            f"deg={deg*100:+.2f}%  (n={raw['n_samples']} wells={raw['n_wells']})")

    degs = [v["degradation"] for v in per_curve.values()]
    summary = dict(levels=list(levels), codebook_size=int(np.prod(levels)),
                   patch=FT.PATCH, epochs=epochs, cap=cap,
                   per_curve=per_curve,
                   n_curves_scored=len(degs),
                   median_degradation=(float(np.median(degs)) if degs else None),
                   max_degradation=(float(np.max(degs)) if degs else None),
                   bar_median_le_5pct=(bool(np.median(degs) <= 0.05) if degs else None),
                   bar_max_le_10pct=(bool(np.max(degs) <= 0.10) if degs else None),
                   elapsed_s=round(time.time() - t0, 1))
    log(f"=== median_deg={summary['median_degradation']} max_deg={summary['max_degradation']} "
        f"(bar: median<=0.05, max<=0.10; REPORT ONLY, advisor gate) elapsed={summary['elapsed_s']}s ===")
    return summary


if __name__ == "__main__":
    # Default full-config single run (NOT the sweep). Kept minimal so accidental invocation is cheap.
    res = run(levels=(8, 5, 5, 5), epochs=8, cap=200_000)
    (OUT / "r8_run.json").write_text(json.dumps(res, indent=2))
    print("R8_RUN_DONE")
