#!/usr/bin/env python3
"""Shared BasinShift evaluation harness (R7 Ruling 2). The single scorer ALL systems flow
through (XGBoost, TS-FM pretrained/control, later S-model/main).

Guarantees:
- Explicit (well, depth_sample) evaluation grid per (direction, target).
- Evaluation-population IDENTITY is asserted before scoring any pair: equal sample count AND
  equal sha256 of the per-well finite-sample mask. Mismatch -> AssertionError (refuse, not warn).
- Scoring is in PHYSICAL units after inverse-transform (resistivity 10**x back from log10;
  identity for DTC/RHOB/NPHI which are stored physical), so normalization gives no system an edge.

Validation (this file's main): reproduce the committed XGBoost baseline
(reports/basinshift/baseline_results.json) THROUGH this harness. If it does not reproduce, STOP.
Read-only over frozen splits (d5b35a00); blind-10 never loaded. Outside the hashed set.
"""
import json, hashlib
from pathlib import Path
import numpy as np, pandas as pd
import pyarrow.parquet as pq
from xgboost import XGBRegressor

ROOT = Path("/workspace/LithoGPT-2")
OUT = ROOT / "reports/basinshift"
SEED = 20260715
CANON = ["GR", "RHOB", "NPHI", "DTC", "PEF", "SP", "CALI", "RDEP", "RMED", "RSHA", "DTS"]
TARGETS = ["DTC", "RHOB", "NPHI"]
MIN_TARGET_SAMPLES = 100
TRAIN_CAP = 1_000_000
LOG10_RESISTIVITY = {"RDEP", "RMED", "RSHA"}
XGB = dict(n_estimators=400, max_depth=6, learning_rate=0.05, subsample=0.8,
           colsample_bytree=0.8, tree_method="hist", random_state=SEED, n_jobs=32)

def inverse_transform(curve, arr):
    """Physical units. Resistivity stored as log10 -> 10**x; else identity (DTC/RHOB/NPHI)."""
    return np.power(10.0, arr) if curve in LOG10_RESISTIVITY else arr

sp = pd.read_csv(ROOT / "data/splits/split_assignment.csv")
sp["well_id"] = sp["well_id"].astype(str); sp["safe_name"] = sp["safe_name"].astype(str)
BLIND = set(sp[sp.split == "blind_force"].well_id) | set(sp[sp.split == "blind_force"].safe_name)

def wells_of(src, split):
    r = sp[(sp.source == src) & (sp.split == split)]
    return [(src, row.safe_name, row.well_id) for row in r.itertuples()]

POOLS = {k: wells_of(*v) for k, v in {
    "kgs_train": ("kgs", "train"), "nlog_train": ("nlog", "train"),
    "force_train": ("force2020", "train"), "test_kgs": ("kgs", "test_kgs"),
    "open10": ("force2020", "test_force_open")}.items()}
RUNS = [("A_cross_to_norway", ["kgs_train", "nlog_train"], "open10"),
        ("B_cross_to_kansas", ["nlog_train", "force_train"], "test_kgs"),
        ("C1_in_kansas", ["kgs_train"], "test_kgs"),
        ("C2_in_norway", ["force_train"], "open10")]

CACHE = {}
def load_well(src, safe, wid):
    key = (src, safe)
    if key in CACHE: return CACHE[key]
    if str(wid) in BLIND or str(safe) in BLIND: raise RuntimeError(f"REFUSED blind {src}/{safe}")
    df = pq.read_table(ROOT / f"data/processed/{src}/{safe}.parquet").to_pandas()
    # float32 to match the committed baseline's dtype EXACTLY (reproduction) and halve memory/time
    cols = {"depth_m": df["depth_m"].to_numpy("float64").astype("float32")}
    for c in CANON:
        v = df[c].to_numpy("float64"); m = df[c + "_mask"].to_numpy().astype(bool)
        cols[c] = np.where(m, v, np.nan).astype("float32")
    out = pd.DataFrame(cols); CACHE[key] = out; return out

def feats_for(t): return [c for c in CANON if c != t] + ["depth_m"]

# ---------------- SHARED SCORER ----------------
def build_grid(test_pool, target):
    """Explicit (well, depth_sample) grid: per scoreable well, the valid target indices +
    physical-unit ground truth. Returns grid list and a population signature."""
    grid = []
    for (src, safe, wid) in POOLS[test_pool]:
        df = load_well(src, safe, wid)
        y = df[target].to_numpy()
        valid = np.where(~np.isnan(y))[0]
        if len(valid) < MIN_TARGET_SAMPLES: continue
        grid.append((wid, valid, inverse_transform(target, y[valid])))
    return grid

def population_signature(grid):
    h = hashlib.sha256()
    n = 0
    for (wid, valid, _y) in sorted(grid, key=lambda g: g[0]):
        h.update(str(wid).encode()); h.update(valid.astype("int64").tobytes()); n += len(valid)
    return n, h.hexdigest()

def score(grid, preds_by_well, target):
    """preds_by_well: {well_id: pred_array aligned to that well's grid valid indices}, in the
    same (physical) space. Asserts population identity, returns physical-unit metrics."""
    gwells = {wid: (valid, y) for (wid, valid, y) in grid}
    assert set(preds_by_well) == set(gwells), "POPULATION MISMATCH: well set differs (refuse)"
    P, T, per_well = [], [], []
    for wid in sorted(gwells):
        valid, y = gwells[wid]; p = np.asarray(preds_by_well[wid], dtype="float64")
        assert len(p) == len(valid), f"POPULATION MISMATCH well {wid}: {len(p)} vs {len(valid)}"
        P.append(p); T.append(y)
        per_well.append(float(np.sqrt(np.mean((p - y) ** 2))))
    P = np.concatenate(P); T = np.concatenate(T)
    return dict(pooled_rmse=float(np.sqrt(np.mean((P - T) ** 2))),
                pooled_mae=float(np.mean(np.abs(P - T))),
                macro_well_rmse=float(np.mean(per_well)),
                n_samples=int(len(T)), n_wells=len(per_well))

# ---------------- XGBoost ADAPTER (mirrors committed baseline exactly) ----------------
rng = np.random.default_rng(SEED)
def build_train(train_pools, target):
    feats = feats_for(target); Xs, ys = [], []
    for p in train_pools:
        for (src, safe, wid) in POOLS[p]:
            df = load_well(src, safe, wid); y = df[target].to_numpy(); v = ~np.isnan(y)
            if v.sum() == 0: continue
            Xs.append(df[feats].to_numpy()[v]); ys.append(y[v])
    X = np.vstack(Xs); y = np.concatenate(ys)
    if len(y) > TRAIN_CAP:
        idx = rng.choice(len(y), TRAIN_CAP, replace=False); X, y = X[idx], y[idx]
    return X, y

def xgb_preds(train_pools, target, grid):
    feats = feats_for(target)
    Xtr, ytr = build_train(train_pools, target)
    m = XGBRegressor(**XGB); m.fit(Xtr, ytr)
    preds = {}
    for (wid, valid, _y) in grid:
        src, safe = next((s, sn) for (s, sn, w) in POOLS_ALL if w == wid)
        df = load_well(src, safe, wid)
        Xte = df[feats].to_numpy()[valid]
        preds[wid] = inverse_transform(target, m.predict(Xte))
    return preds

POOLS_ALL = [(s, sn, w) for pool in POOLS.values() for (s, sn, w) in pool]

# ---------------- VALIDATION ----------------
committed = json.loads((OUT / "baseline_results.json").read_text())
lines = []
def log(*a): s = " ".join(str(x) for x in a); print(s); lines.append(s)

log("=== Shared eval harness: reproduce committed XGBoost baseline (physical units) ===")
allpass = True
for (name, train_pools, test_pool) in RUNS:
    for tgt in TARGETS:
        grid = build_grid(test_pool, tgt)
        n, sig = population_signature(grid)
        # scorer sanity: truth-as-pred -> 0
        zero = score(grid, {wid: y for (wid, valid, y) in grid}, tgt)["pooled_rmse"]
        preds = xgb_preds(train_pools, tgt, grid)
        got = score(grid, preds, tgt)
        c = committed[name]["targets"][tgt]
        d_rmse = abs(got["pooled_rmse"] - c["pooled_rmse"])
        d_mae = abs(got["pooled_mae"] - c["pooled_mae"])
        d_macro = abs(got["macro_well_rmse"] - c["macro_well_rmse"])
        ok = (got["n_samples"] == c["n_samples"] and got["n_wells"] == c["test_wells_scored"]
              and d_rmse < 1e-4 and d_mae < 1e-4 and d_macro < 1e-4 and zero < 1e-9)
        allpass &= ok
        log(f"[{name}/{tgt}] n={got['n_samples']} (committed {c['n_samples']}) wells={got['n_wells']} "
            f"popsig={sig[:12]} truth0={zero:.2e}")
        log(f"    RMSE harness={got['pooled_rmse']:.4f} committed={c['pooled_rmse']:.4f} d={d_rmse:.2e} | "
            f"MAE {got['pooled_mae']:.4f}/{c['pooled_mae']:.4f} d={d_mae:.2e} | "
            f"macro {got['macro_well_rmse']:.4f}/{c['macro_well_rmse']:.4f} d={d_macro:.2e}  -> {'PASS' if ok else 'FAIL'}")

log(f"\n=== HARNESS VALIDATION: {'ALL PASS (reproduces committed XGBoost)' if allpass else 'FAILURE'} ===")
(OUT / "harness_validation.txt").write_text("\n".join(lines) + "\n")
print("HARNESS_VALIDATION_DONE" if allpass else "HARNESS_VALIDATION_FAILED")
