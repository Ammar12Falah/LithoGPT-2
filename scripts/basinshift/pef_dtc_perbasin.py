#!/usr/bin/env python3
"""Cheap per-basin PEF/DTC derivation from saved artifacts + raw arm ONLY (NO reconstruction).
Delivers: per-basin RAW imputation RMSE + well/sample counts for PEF and DTC (global imputer,
per-basin eval); PEF TRAIN patch-bank composition by source basin (patch 32 and 16); dev well
counts per basin. The recon-dependent DEGRADATION split is NOT computed here (needs re-running
reconstruction) -- see report for its cost."""
import json
import numpy as np
from xgboost import XGBRegressor
import eval_harness as EH
import fsq_tokenizer as FT
import fsq_diag as D

OUT = EH.ROOT / "reports/basinshift/fsq_diag"
GLOBAL_TRAIN = [w for k in ["kgs_train", "nlog_train", "force_train"] for w in EH.POOLS[k]]
DEVS = [("KGS_dev", EH.wells_of("kgs", "dev")),
        ("NLOG_Netherlands_dev", EH.wells_of("nlog", "dev"))]

res = {"note": "RAW arm only, NO reconstruction. Degradation split needs recon (not run here).",
       "xgb_params": {k: (v if not isinstance(v, float) else v) for k, v in EH.XGB.items()},
       "seed": EH.SEED, "train_cap": EH.TRAIN_CAP, "patch_min_valid_frac": 0.5}

res["per_basin_raw"] = {}
for C in ["PEF", "DTC"]:
    Xtr, ytr = D.build_train_pool(GLOBAL_TRAIN, C)
    m = XGBRegressor(**EH.XGB); m.fit(Xtr, ytr)
    for bname, wells in DEVS:
        g5 = D.grid_pool(wells, C)
        if not g5:
            res["per_basin_raw"][f"{C}|{bname}"] = dict(raw_rmse=None, n_wells=0, n_samples=0)
            continue
        sc = D.score3(g5, D.predict_grid(C, m, g5, recon_map=None), C)
        res["per_basin_raw"][f"{C}|{bname}"] = dict(raw_rmse=sc["pooled_rmse"],
                                                    n_wells=sc["n_wells"], n_samples=sc["n_samples"])
        print(f"[raw {C}/{bname}] raw_RMSE={sc['pooled_rmse']:.6g} wells={sc['n_wells']} n={sc['n_samples']}", flush=True)

res["pef_bank_composition"] = {}
for patch in [32, 16]:
    comp = {}
    for basin, key in [("KGS", "kgs_train"), ("NLOG_Netherlands", "nlog_train"), ("FORCE_Norway", "force_train")]:
        cnt = 0
        for (s, sf, w) in EH.POOLS[key]:
            a = EH.load_well(s, sf, w)["PEF"].to_numpy()
            finite = np.isfinite(a).astype("float32")
            fm, _ = FT.patchify(finite, patch)
            cnt += int((fm.mean(axis=1) >= 0.5).sum())
        comp[basin] = cnt
        print(f"[PEF bank patch{patch}/{basin}] patches={cnt}", flush=True)
    comp["TOTAL"] = comp["KGS"] + comp["NLOG_Netherlands"] + comp["FORCE_Norway"]
    res["pef_bank_composition"][f"patch{patch}"] = comp

res["dev_well_counts"] = {}
for C in ["PEF", "DTC"]:
    for bname, wells in DEVS:
        g5 = D.grid_pool(wells, C)
        res["dev_well_counts"][f"{C}|{bname}"] = dict(
            n_wells=len(g5), n_samples=int(sum(len(v) for _, v, _, _, _ in g5)))
        print(f"[devcount {C}/{bname}] wells={len(g5)}", flush=True)

(OUT / "pef_dtc_perbasin.json").write_text(json.dumps(res, indent=2))
print("PERBASIN_DONE", flush=True)
