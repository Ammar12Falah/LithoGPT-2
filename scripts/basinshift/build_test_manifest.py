#!/usr/bin/env python3
"""Freeze the BasinShift test manifest (roadmap 6.1, Phase 2).

Builds the immutable test-set definition from the frozen splits (d5b35a00) ONLY, folds the
n=9 Kansas-DTC thin-cell caveat INSIDE the artifact, writes it canonically (sorted keys), and
computes its sha256. Blind-10 (split==blind_force) is asserted absent from every test pool and
its DATA is never loaded (only names). Outside the hashed set; does not move d5b35a00.
"""
import json, hashlib
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq

ROOT = Path("/workspace/LithoGPT-2")
OUT = ROOT / "reports/basinshift"
MANIFEST = OUT / "basinshift_test_manifest.json"
SHAFILE = OUT / "basinshift_test_manifest.sha256"
TARGETS = ["DTC", "RHOB", "NPHI"]
MIN_TARGET_SAMPLES = 100

import pandas as pd
sp = pd.read_csv(ROOT / "data/splits/split_assignment.csv")
sp["well_id"] = sp["well_id"].astype(str); sp["safe_name"] = sp["safe_name"].astype(str)
BLIND = set(sp[sp.split == "blind_force"].well_id) | set(sp[sp.split == "blind_force"].safe_name)

def pool_wells(src, split):
    r = sp[(sp.source == src) & (sp.split == split)].sort_values("well_id")
    return [dict(well_id=row.well_id, safe_name=row.safe_name, source=src, split=split)
            for row in r.itertuples()]

TEST_POOLS = {
    "force2020:test_force_open": pool_wells("force2020", "test_force_open"),
    "kgs:test_kgs": pool_wells("kgs", "test_kgs"),
}

def valid_count(src, safe, target):
    if safe in BLIND or src == "force2020" and safe in BLIND:
        raise RuntimeError(f"REFUSED blind load {src}/{safe}")
    t = pq.read_table(ROOT / f"data/processed/{src}/{safe}.parquet", columns=[target, target + "_mask"])
    m = t.column(target + "_mask").to_numpy().astype(bool)
    v = t.column(target).to_numpy(zero_copy_only=False)
    return int(np.sum(m & ~np.isnan(np.asarray(v, dtype="float64"))))

# scoreable-well counts per (test_pool, target)
scoreable = {}
for pkey, wells in TEST_POOLS.items():
    for w in wells:
        assert w["well_id"] not in BLIND and w["safe_name"] not in BLIND, f"BLIND in {pkey}: {w}"
    scoreable[pkey] = {}
    for tgt in TARGETS:
        n = sum(1 for w in wells if valid_count(w["source"], w["safe_name"], tgt) >= MIN_TARGET_SAMPLES)
        scoreable[pkey][tgt] = n

manifest = {
    "benchmark": "BasinShift",
    "version": "1.0",
    "frozen_against": {
        "corpus_manifest_sha256": "d5b35a00ffa49aab7f7e634013c238aa1fc989a17e3ad1c5a5d83f7606e3a8a9",
        "split_gen_commit": "d4113797cbd2885f4585004b754fc9856527a6c9",
        "seed": 20260715,
    },
    "task": "cross-basin curve imputation: hide one canonical target curve per config, predict per depth-sample from the remaining canonical log curves + depth_m",
    "targets_hidden": TARGETS,
    "scoring": {
        "metrics": ["RMSE", "MAE"],
        "aggregation": ["pooled_over_samples", "macro_over_wells"],
        "min_target_samples_to_score": MIN_TARGET_SAMPLES,
        "reporting_rule": "every reported RMSE MUST be accompanied by its scored well count; never RMSE alone. This is mandatory for the Kansas-DTC cell (n=9).",
    },
    "directions": {
        "A_cross_to_norway": {"kind": "cross-basin", "train_splits": ["kgs:train", "nlog:train"], "test_pool": "force2020:test_force_open"},
        "B_cross_to_kansas": {"kind": "cross-basin", "train_splits": ["nlog:train", "force2020:train"], "test_pool": "kgs:test_kgs"},
        "C1_in_kansas": {"kind": "in-basin", "train_splits": ["kgs:train"], "test_pool": "kgs:test_kgs"},
        "C2_in_norway": {"kind": "in-basin", "train_splits": ["force2020:train"], "test_pool": "force2020:test_force_open"},
    },
    "test_pools": {k: {"n_wells": len(v), "wells": v} for k, v in TEST_POOLS.items()},
    "scoreable_wells_by_target": scoreable,
    "caveats": {
        "kansas_DTC": "n=9, low well support, wide uncertainty. Only 9 of 263 test_kgs wells carry >=100 valid DTC (sonic) samples (Kansas rarely logs sonic). This cell (directions B and C1, target DTC) is RETAINED as a true fact about the data, not dropped. Any Kansas-DTC RMSE MUST be reported with n=9 alongside it, never RMSE alone."
    },
    "blind_rule": "FORCE blind-10 (split==blind_force) is never in any test pool and its DATA is never loaded (only names, for the absence assertion). Touched once by the final scoring path at G3 (roadmap 6.6).",
    "provenance": "built from data/splits/split_assignment.csv at freeze d5b35a00; evidence artifact outside the hashed set; does not move qc_code_sha256 or d5b35a00.",
}

# sanity: caveat matches computed n
assert scoreable["kgs:test_kgs"]["DTC"] == 9, f"Kansas-DTC scoreable != 9: {scoreable['kgs:test_kgs']['DTC']}"

blob = json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
MANIFEST.write_text(blob, encoding="utf-8")
h = hashlib.sha256(blob.encode("utf-8")).hexdigest()
SHAFILE.write_text(f"{h}  basinshift_test_manifest.json\n")
print("BASINSHIFT_TEST_MANIFEST_SHA256:", h)
print("scoreable_wells_by_target:", json.dumps(scoreable))
print("test pools:", {k: len(v) for k, v in TEST_POOLS.items()})
print("MANIFEST_BUILT_DONE")
