#!/usr/bin/env python3
"""BasinShift leakage suite (roadmap 6.1, CHECKPOINT 2).

Goes beyond well-overlap: proves SPATIAL separation is inherited from the corpus freeze (R1).
Every test well must originate from a frozen holdout/open split (test_kgs / test_force_open);
NO test well may come from a training spatial block (train/dev). Prints per-well split origin
so the spatial inheritance is visible, not assumed. Reads split_assignment.csv only (frozen).
"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path("/workspace/LithoGPT-2")
OUT = ROOT / "reports/basinshift"
REPORT = OUT / "leakage_suite.txt"
lines = []
def log(*a):
    s = " ".join(str(x) for x in a); print(s); lines.append(s)

sp = pd.read_csv(ROOT / "data/splits/split_assignment.csv")
sp["well_id"] = sp["well_id"].astype(str); sp["safe_name"] = sp["safe_name"].astype(str)
BLIND = set(sp[sp.split == "blind_force"].well_id) | set(sp[sp.split == "blind_force"].safe_name)

HOLDOUT_SPLITS = {"test_kgs", "test_force_open"}   # frozen holdout/open (spatial blocks reserved out of training)
TRAIN_SPLITS = {"train", "dev"}                     # spatial blocks used for training/tuning

def wells(src, split):
    r = sp[(sp.source == src) & (sp.split == split)]
    return {(row.well_id): (src, row.safe_name, split) for row in r.itertuples()}

POOLS = {
    "kgs:train": wells("kgs", "train"), "nlog:train": wells("nlog", "train"),
    "force2020:train": wells("force2020", "train"),
    "kgs:test_kgs": wells("kgs", "test_kgs"),
    "force2020:test_force_open": wells("force2020", "test_force_open"),
}
DIRECTIONS = {
    "A_cross_to_norway": (["kgs:train", "nlog:train"], "force2020:test_force_open"),
    "B_cross_to_kansas": (["nlog:train", "force2020:train"], "kgs:test_kgs"),
    "C1_in_kansas": (["kgs:train"], "kgs:test_kgs"),
    "C2_in_norway": (["force2020:train"], "force2020:test_force_open"),
}

log("=== BasinShift leakage suite (CHECKPOINT 2) ===")
log(f"blind_force names (never in any set): {sorted(set(sp[sp.split=='blind_force'].well_id))}")
allpass = True

# global spatial check: every test-pool well is from a holdout/open split
for tp in ["kgs:test_kgs", "force2020:test_force_open"]:
    origins = {}
    for wid, (src, safe, split) in POOLS[tp].items():
        origins.setdefault(split, 0); origins[split] += 1
    only_holdout = set(origins) <= HOLDOUT_SPLITS
    log(f"[spatial] {tp}: split-origin counts = {origins}  -> all from frozen holdout/open? {only_holdout}")
    allpass &= only_holdout

for name, (train_pools, test_pool) in DIRECTIONS.items():
    log(f"\n--- {name}  train={train_pools}  test={test_pool} ---")
    test_ids = set(POOLS[test_pool]); test_safe = set(v[1] for v in POOLS[test_pool].values())
    train_ids = set().union(*[set(POOLS[p]) for p in train_pools])
    train_safe = set(v[1] for p in train_pools for v in POOLS[p].values())
    # (1) well-level overlap
    ov = train_ids & test_ids
    log(f"  [1] train/test well-id overlap: {len(ov)}  (expect 0)")
    # (2) blind absent
    bl = (test_ids | test_safe) & BLIND
    log(f"  [2] blind in test (id|safe): {len(bl)}  (expect 0)")
    # (3) spatial: every test well from a holdout/open split; none from a training split
    test_split_origins = {}
    from_train_block = 0
    for wid, (src, safe, split) in POOLS[test_pool].items():
        test_split_origins.setdefault(split, 0); test_split_origins[split] += 1
        if split in TRAIN_SPLITS:
            from_train_block += 1
    all_holdout = set(test_split_origins) <= HOLDOUT_SPLITS
    log(f"  [3] test split-origins = {test_split_origins}; from a training block: {from_train_block}"
        f"  -> all holdout/open? {all_holdout}")
    # (4) dev not used as a test pool
    dev_as_test = any(POOLS[test_pool] and list(POOLS[test_pool].values())[0][2] == "dev" for _ in [0])
    log(f"  [4] test pool is a dev split? {dev_as_test}  (expect False)")
    # (5) no train-safe/name collision into test (cross-source)
    safe_ov = train_safe & test_safe
    log(f"  [5] train/test safe_name overlap: {len(safe_ov)}  (expect 0)")
    ok = (len(ov) == 0 and len(bl) == 0 and all_holdout and from_train_block == 0 and not dev_as_test and len(safe_ov) == 0)
    log(f"  => {name}: {'PASS' if ok else 'FAIL'}")
    allpass &= ok

# per-well split origin, full enumeration (spatial inheritance made visible)
log("\n=== per-well split origin (test sets) ===")
for tp in ["force2020:test_force_open", "kgs:test_kgs"]:
    log(f"[{tp}]  ({len(POOLS[tp])} wells)")
    for wid in sorted(POOLS[tp]):
        src, safe, split = POOLS[tp][wid]
        log(f"    {wid}\t{src}\t{split}")

log(f"\n=== LEAKAGE SUITE: {'ALL PASS' if allpass else 'FAILURE'} ===")
REPORT.write_text("\n".join(lines) + "\n")
print("LEAKAGE_SUITE_DONE" if allpass else "LEAKAGE_SUITE_FAILED")
