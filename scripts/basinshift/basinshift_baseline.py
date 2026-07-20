#!/usr/bin/env python3
"""BasinShift eval-set assembly + XGBoost baseline (roadmap 6.1, Phase 1).

OUTSIDE the hashed set. Builds ONLY against the frozen splits (manifest d5b35a00);
does not reopen ingestion, re-cut splits, or synthesise data. Rule 14: every count,
assertion, and metric it produces is written to reports/basinshift/ at run time.

Blind rule: FORCE blind-10 (split == 'blind_force') DATA is never loaded. Only its
names are read, and every assembled set is asserted free of blind names. The blind
parquets are not even present in data/processed/force2020 (108 = 98 train + 10 open);
this script additionally refuses to open any blind path.

Task: curve imputation. Hide one canonical target curve (DTC / RHOB / NPHI) per config,
predict it per depth-sample from the remaining canonical log curves + depth_m.
Score per-curve RMSE and MAE (pooled over valid test target samples; per-well macro mean
reported alongside). XGBoost is the standing baseline opponent.
"""
import json, glob, os, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from xgboost import XGBRegressor

ROOT = Path("/workspace/LithoGPT-2")
OUT = ROOT / "reports/basinshift"
OUT.mkdir(parents=True, exist_ok=True)
LOG = open(OUT / "run_log.txt", "w")
SEED = 20260715
rng = np.random.default_rng(SEED)

CANON = ["GR", "RHOB", "NPHI", "DTC", "PEF", "SP", "CALI", "RDEP", "RMED", "RSHA", "DTS"]
TARGETS = ["DTC", "RHOB", "NPHI"]
MIN_TARGET_SAMPLES = 100          # a test well must have >= this many valid target samples to be scored
TRAIN_CAP = 1_000_000             # per-fit training-sample cap (seeded subsample above it)
XGB = dict(n_estimators=400, max_depth=6, learning_rate=0.05, subsample=0.8,
           colsample_bytree=0.8, tree_method="hist", random_state=SEED, n_jobs=32)

def log(*a):
    s = " ".join(str(x) for x in a)
    print(s); LOG.write(s + "\n"); LOG.flush()

# ---- splits ----
sp = pd.read_csv(ROOT / "data/splits/split_assignment.csv")
sp["well_id"] = sp["well_id"].astype(str)
sp["safe_name"] = sp["safe_name"].astype(str)
BLIND = sp[sp.split == "blind_force"]
BLIND_IDS = set(BLIND.well_id) | set(BLIND.safe_name)
log(f"[splits] blind_force wells (never loaded): {len(BLIND)}  names={sorted(set(BLIND.well_id))}")

def wells_of(src, split):
    r = sp[(sp.source == src) & (sp.split == split)]
    return [(src, row.safe_name, row.well_id) for row in r.itertuples()]

POOLS = {
    "kgs_train":   wells_of("kgs", "train"),
    "nlog_train":  wells_of("nlog", "train"),
    "force_train": wells_of("force2020", "train"),
    "test_kgs":    wells_of("kgs", "test_kgs"),
    "open10":      wells_of("force2020", "test_force_open"),
}
for k, v in POOLS.items():
    log(f"[pool] {k}: {len(v)} wells")

# ---- well cache (load each needed well ONCE, masked, float32) ----
CACHE = {}
def load_well(src, safe, wid):
    key = (src, safe)
    if key in CACHE:
        return CACHE[key]
    if str(wid) in BLIND_IDS or str(safe) in BLIND_IDS:
        raise RuntimeError(f"REFUSED blind well load: {src}/{safe}")  # blind tripwire
    p = ROOT / f"data/processed/{src}/{safe}.parquet"
    df = pq.read_table(p).to_pandas()
    depth = df["depth_m"].to_numpy(dtype="float64")
    cols = {"depth_m": depth.astype("float32")}
    for c in CANON:
        v = df[c].to_numpy(dtype="float64")
        m = df[c + "_mask"].to_numpy().astype(bool)
        cols[c] = np.where(m, v, np.nan).astype("float32")
    out = pd.DataFrame(cols)
    CACHE[key] = out
    return out

def feats_for(target):
    return [c for c in CANON if c != target] + ["depth_m"]

def build_train(pool_wells, target):
    feats = feats_for(target)
    Xs, ys = [], []
    for (src, safe, wid) in pool_wells:
        df = load_well(src, safe, wid)
        y = df[target].to_numpy()
        valid = ~np.isnan(y)
        n = int(valid.sum())
        if n == 0:
            continue
        Xs.append(df[feats].to_numpy()[valid]); ys.append(y[valid])
    if not Xs:
        return None, None
    X = np.vstack(Xs); y = np.concatenate(ys)
    if len(y) > TRAIN_CAP:
        idx = rng.choice(len(y), TRAIN_CAP, replace=False)
        X, y = X[idx], y[idx]
    return X, y

def build_test(pool_wells, target):
    """Return per-well test arrays, only for wells with >= MIN_TARGET_SAMPLES valid target."""
    feats = feats_for(target)
    kept, dropped = [], []
    for (src, safe, wid) in pool_wells:
        df = load_well(src, safe, wid)
        y = df[target].to_numpy()
        valid = ~np.isnan(y)
        if int(valid.sum()) < MIN_TARGET_SAMPLES:
            dropped.append((wid, int(valid.sum()))); continue
        kept.append((wid, df[feats].to_numpy()[valid], y[valid]))
    return kept, dropped

def score(model, kept):
    all_p, all_t, per_well = [], [], []
    for (wid, X, y) in kept:
        pred = model.predict(X)
        all_p.append(pred); all_t.append(y)
        rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
        per_well.append((wid, len(y), rmse))
    P = np.concatenate(all_p); T = np.concatenate(all_t)
    pooled_rmse = float(np.sqrt(np.mean((P - T) ** 2)))
    pooled_mae = float(np.mean(np.abs(P - T)))
    macro_rmse = float(np.mean([r for (_, _, r) in per_well]))
    return dict(pooled_rmse=pooled_rmse, pooled_mae=pooled_mae, macro_well_rmse=macro_rmse,
                n_samples=int(len(T)), n_wells=len(per_well))

# ---- runs: (name, train pools, test pool, direction label) ----
RUNS = [
    ("A_cross_to_norway", ["kgs_train", "nlog_train"], "open10",   "cross-basin -> Norway (open-10)"),
    ("B_cross_to_kansas", ["nlog_train", "force_train"], "test_kgs", "cross-basin -> Kansas (test_kgs)"),
    ("C1_in_kansas",      ["kgs_train"], "test_kgs",  "in-basin -> Kansas (test_kgs)"),
    ("C2_in_norway",      ["force_train"], "open10",  "in-basin -> Norway (open-10)"),
]

def assert_clean(run_name, train_pools, test_pool):
    test_wells = POOLS[test_pool]
    test_ids = set(w[2] for w in test_wells); test_safe = set(w[1] for w in test_wells)
    # (1) no blind
    bl = (test_ids | test_safe) & BLIND_IDS
    assert not bl, f"{run_name}: BLIND well in test set: {bl}"
    # (2) no train/test leak
    train_ids = set(w[2] for p in train_pools for w in POOLS[p])
    leak = train_ids & test_ids
    assert not leak, f"{run_name}: train well leaked into test: {leak}"
    # (3) test wells all from the intended holdout/open split (by construction of POOLS)
    return dict(test_ids=len(test_ids), train_ids=len(train_ids), blind_overlap=0, train_test_overlap=0)

# ---- execute ----
t0 = time.time()
results = {}
composition = {}
for (name, train_pools, test_pool, label) in RUNS:
    log(f"\n===== RUN {name}  [{label}] =====")
    chk = assert_clean(name, train_pools, test_pool)
    log(f"  assertions PASS: blind_overlap=0 train_test_overlap=0 "
        f"(train wells={chk['train_ids']}, test wells={chk['test_ids']})")
    results[name] = {"label": label, "train_pools": train_pools, "test_pool": test_pool, "targets": {}}
    composition[name] = {"label": label, "train_pools": {p: len(POOLS[p]) for p in train_pools},
                         "test_pool": {test_pool: len(POOLS[test_pool])}, "per_target": {}}
    for tgt in TARGETS:
        Xtr, ytr = build_train([w for p in train_pools for w in POOLS[p]], tgt)
        kept, dropped = build_test(POOLS[test_pool], tgt)
        if Xtr is None or not kept:
            log(f"  [{tgt}] SKIP (no train or no scoreable test wells)"); continue
        m = XGBRegressor(**XGB)
        m.fit(Xtr, ytr)
        sc = score(m, kept)
        # global-mean floor for context
        gm = float(np.mean(ytr))
        floor_rmse = float(np.sqrt(np.mean((np.concatenate([y for (_, _, y) in kept]) - gm) ** 2)))
        sc["train_samples_used"] = int(len(ytr))
        sc["test_wells_scored"] = len(kept)
        sc["test_wells_dropped_lt_min"] = len(dropped)
        sc["global_mean_floor_rmse"] = floor_rmse
        results[name]["targets"][tgt] = sc
        composition[name]["per_target"][tgt] = {"scored_wells": len(kept), "dropped_wells": len(dropped),
                                                 "test_samples": sc["n_samples"]}
        log(f"  [{tgt}] train_n={sc['train_samples_used']} test_wells={sc['test_wells_scored']}"
            f"(dropped {len(dropped)}) samples={sc['n_samples']}  "
            f"RMSE={sc['pooled_rmse']:.4f} MAE={sc['pooled_mae']:.4f} "
            f"macro_well_RMSE={sc['macro_well_rmse']:.4f} (floor {floor_rmse:.4f})")

log(f"\n[done] wells cached: {len(CACHE)}  elapsed {time.time()-t0:.1f}s")

# ---- proposed test manifest (NOT hashed; CP1 review artifact) ----
proposed = {
    "benchmark": "BasinShift",
    "frozen_against": "corpus_manifest d5b35a00",
    "note": "PROPOSED for CHECKPOINT 1 review. NOT hashed. Test manifest becomes immutable only after Plan clears CP1 (Phase 2).",
    "targets_hidden": TARGETS,
    "min_target_samples_to_score": MIN_TARGET_SAMPLES,
    "directions": {},
}
for (name, train_pools, test_pool, label) in RUNS:
    tw = POOLS[test_pool]
    proposed["directions"][name] = {
        "label": label,
        "train_pools": {p: len(POOLS[p]) for p in train_pools},
        "test_pool": test_pool,
        "test_wells": sorted(w[2] for w in tw),
        "n_test_wells": len(tw),
    }
(OUT / "test_manifest_PROPOSED.json").write_text(json.dumps(proposed, indent=2))
(OUT / "baseline_results.json").write_text(json.dumps(results, indent=2))
(OUT / "eval_composition.json").write_text(json.dumps(composition, indent=2))
log("[written] reports/basinshift/{run_log.txt,baseline_results.json,eval_composition.json,test_manifest_PROPOSED.json}")
LOG.close()
print("BASINSHIFT_BASELINE_DONE")
