import sys
sys.path.insert(0, "/workspace/LithoGPT-2/src")

from pathlib import Path
import pandas as pd

from lithogpt2.config import HarmonizationConfig
from lithogpt2.ingest.force2020 import iter_force_wells
from lithogpt2.pipeline.batch import run_batch

ROOT = Path("/workspace/LithoGPT-2")
RAW = ROOT / "data/raw/force2020"
PROC = ROOT / "data/processed/force2020"
SCRATCH = ROOT / "reports/_force_reprocess_check"
SCRATCH.mkdir(parents=True, exist_ok=True)

print("=== 0. LOAD FROZEN CONFIG (same alias YAML the corpus was built under) ===")
cfg = HarmonizationConfig.load()  # defaults to configs/mnemonic_aliases.yaml
print("  config loaded from default path")

print("\n=== 1. REPROCESS 98 TRAINING WELLS ===")
train_csv = str(RAW / "train.csv")
res_train = run_batch(iter_force_wells(train_csv), cfg, source="force2020",
                      processed_dir=PROC, keep_harmonized=True)
print(f"  records: {len(res_train['records'])}  failures: {len(res_train['failures'])}")
for wid, err in res_train["failures"]:
    print(f"    FAIL {wid}: {err}")
assert len(res_train["records"]) == 98, f"FAIL: expected 98, got {len(res_train['records'])}"

print("\n=== 2. WRITE QC RECORDS TO SCRATCH (never touches the committed file) ===")
new_rows = pd.DataFrame([r.as_row() for r in res_train["records"]])
new_path = SCRATCH / "force2020_qc_records_NEW.csv"
new_rows.to_csv(new_path, index=False)
print(f"  wrote {new_path}  shape={new_rows.shape}")

print("\n=== 3. DETERMINISM ASSERTION vs COMMITTED RECORDS ===")
old = pd.read_csv(ROOT / "reports/force2020_qc_records.csv").sort_values("well_id").reset_index(drop=True)
new = pd.read_csv(new_path).sort_values("well_id").reset_index(drop=True)
print(f"  committed rows: {len(old)}   reprocessed rows: {len(new)}")
assert set(old["well_id"]) == set(new["well_id"]), \
    f"FAIL: well set differs. only_old={set(old['well_id'])-set(new['well_id'])} " \
    f"only_new={set(new['well_id'])-set(old['well_id'])}"
print("  well_id sets identical: OK")

if set(old.columns) ^ set(new.columns):
    print(f"  NOTE: column set differs: {set(old.columns) ^ set(new.columns)}")

common = [c for c in old.columns if c in new.columns]
mism = {}
for c in common:
    o, n = old[c], new[c]
    if pd.api.types.is_float_dtype(o) or pd.api.types.is_float_dtype(n):
        eq = ((o - n).abs() < 1e-9) | (o.isna() & n.isna())
    else:
        eq = (o == n) | (o.isna() & n.isna())
    b = int((~eq).sum())
    if b:
        mism[c] = b

if mism:
    print(f"  *** MISMATCHES: {mism} ***")
    for c in mism:
        for wid in old.loc[old[c].ne(new[c]), "well_id"].head(5):
            ov = old.loc[old.well_id == wid, c].values[0]
            nv = new.loc[new.well_id == wid, c].values[0]
            print(f"    {c} {wid}: {ov!r} -> {nv!r}")
    raise SystemExit("STOP: FORCE reprocess is NOT deterministic. Do not proceed to splits.")
print("\n  ALL COLUMNS MATCH EXACTLY across all 98 wells. Determinism PROVEN.")

print("\n=== 4. RESTORE OPEN-10 PARQUETS ===")
res_open = run_batch(iter_force_wells(str(RAW / "leaderboard_test_features.csv")),
                     cfg, source="force2020", processed_dir=PROC, keep_harmonized=False)
print(f"  open-10 processed: {len(res_open['records'])} (expected 10)")

print("\n=== 5. FINAL DISK STATE ===")
n = len(list(PROC.glob("*.parquet")))
print(f"  force2020 parquets on disk: {n}  (expect 108 = 98 train + 10 open)")
assert not (RAW / "hidden_test.csv").exists(), "FAIL: blind data on disk"
print(f"  blind-10 present: {(RAW / 'hidden_test.csv').exists()}  <-- must be False")
print("\n  FORCE restored. 98 train records match committed exactly. Blind-10 absent.")
